import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import CORRECT_POINTS
from database import (
    add_points,
    add_group_points,
    record_correct_answer,
    record_group_correct_answer,
    record_group_wrong_answer,
    record_wrong_answer,
    ensure_player,
    ensure_group_player,
)
from utils.helpers import safe_task, safe_delete_message
from utils.shuffle import shuffle_question

from handlers.challenge import active_duels
from handlers.game_results import end_game
from handlers.game_setup import load_dynamic_settings

from services.game_service import (
    active_games,
    poll_map,
    get_game_lock,
    start_next_round,
    prepare_round_state,
    apply_poll_answer,
    get_unused_question,
)

logger = logging.getLogger(__name__)


def row_value(row, key, default=None):
    if row is None:
        return default
    try:
        value = row[key]
        return default if value is None else value
    except Exception:
        return default


def get_question_points(difficulty: str):
    settings = load_dynamic_settings()
    points = settings["POINTS"]

    if not difficulty:
        return points["easy"]
    return points.get(str(difficulty).lower(), points["easy"])


def format_question_text(question: str, points: int) -> str:
    return f"{question}\n🍋 +{points}"


async def send_question(chat_id, context):
    settings = load_dynamic_settings()
    question_seconds = settings["QUESTION_SECONDS"]

    logger.warning("SEND QUESTION: %s", chat_id)

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            return

        current_round, questions_per_game, should_end = start_next_round(game)

    if should_end:
        await end_game(chat_id, context)
        return

    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            return

        try:
            question = get_unused_question(game)
            logger.warning("Fetched game question: %s", dict(question) if question else None)
        except Exception:
            logger.exception("Failed to fetch question for chat %s", chat_id)
            await context.bot.send_message(chat_id, "❌ Failed to load question from database.")
            await end_game(chat_id, context)
            return

        no_question = not question

    if no_question:
        await context.bot.send_message(
            chat_id,
            "No more unused questions available for this category/difficulty.\nEnding game.",
        )
        await end_game(chat_id, context)
        return

    try:
        q_id = question["id"]
        q_text = question["question_text"]
        difficulty = row_value(question, "difficulty", "easy")
        points = get_question_points(difficulty)

        options, correct_index = shuffle_question(question)

        if correct_index not in (0, 1, 2, 3):
            await context.bot.send_message(
                chat_id,
                f"Question ID {q_id} has an invalid correct option.",
            )
            await end_game(chat_id, context)
            return

        poll_question = format_question_text(q_text, points)

        msg = await context.bot.send_poll(
            chat_id=chat_id,
            question=poll_question,
            options=options,
            type="quiz",
            correct_option_id=correct_index,
            is_anonymous=False,
            open_period=question_seconds,
        )
    except Exception:
        logger.exception("Failed to send poll in chat %s round %s", chat_id, current_round)
        await context.bot.send_message(chat_id, "Failed to send the next question.\nEnding game.")
        await end_game(chat_id, context)
        return

    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            poll_map.pop(msg.poll.id, None)
            return

        prepare_round_state(game, msg.poll.id, q_id, correct_index)

    poll_map[msg.poll.id] = {
        "chat_id": chat_id,
        "round": current_round,
        "question_id": q_id,
        "difficulty": difficulty,
        "points": points,
    }

    logger.info("Sent poll %s in chat %s for round %s", msg.poll.id, chat_id, current_round)
    safe_task(wait_and_continue(chat_id, context, msg.poll.id, current_round))


async def wait_and_continue(chat_id, context, poll_id, round_number):
    settings = load_dynamic_settings()
    question_seconds = settings["QUESTION_SECONDS"]

    await asyncio.sleep(question_seconds + 1)

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            poll_map.pop(poll_id, None)
            return

        if game.get("current_poll_id") != poll_id:
            poll_map.pop(poll_id, None)
            return

    poll_map.pop(poll_id, None)
    await send_question(chat_id, context)


async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ignore duel polls so they can be handled by handlers.challenge.handle_duel_poll_answer
    for duel in active_duels.values():
        if duel.get("current_poll_id") == update.poll_answer.poll_id:
            return

    settings = load_dynamic_settings()
    points_map = settings["POINTS"]
    speed_bonus_seconds = settings["SPEED_BONUS_SECONDS"]
    speed_bonus_points = settings["SPEED_BONUS_POINTS"]

    answer = update.poll_answer
    poll_id = answer.poll_id
    info = poll_map.get(poll_id)

    if not info:
        return

    if info.get("round") == "daily":
        user = answer.user
        ensure_player(user)

        if user.id != info.get("daily_user_id"):
            return

        points = info.get("points", CORRECT_POINTS)

        if answer.option_ids and answer.option_ids[0] == info["correct_index"]:
            add_points(user.id, points)
            record_correct_answer(user.id)

            if info["chat_id"] < 0:
                ensure_group_player(info["chat_id"], user)
                add_group_points(info["chat_id"], user, points)
                record_group_correct_answer(info["chat_id"], user)

            display_name = f"@{user.username}" if user.username else user.full_name
            msg = await context.bot.send_message(
                info["chat_id"],
                f"✅ {display_name} +{points} 🍋",
            )
            safe_task(delete_later(context, info["chat_id"], msg.message_id, 4))
        else:
            record_wrong_answer(user.id)

            if info["chat_id"] < 0:
                ensure_group_player(info["chat_id"], user)
                record_group_wrong_answer(info["chat_id"], user)

            msg = await context.bot.send_message(
                info["chat_id"],
                f"🎯 Daily Quiz\n❌ {user.full_name} got it wrong.",
            )
            safe_task(delete_later(context, info["chat_id"], msg.message_id, 4))

        poll_map.pop(poll_id, None)
        return

    chat_id = info["chat_id"]

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game:
            return

        user = answer.user
        ensure_player(user)

        base_points = info.get("points", points_map["easy"])

        result = apply_poll_answer(
            game=game,
            user_id=user.id,
            option_ids=answer.option_ids,
            correct_points=base_points,
            speed_bonus_seconds=speed_bonus_seconds,
            speed_bonus_points=speed_bonus_points,
        )

        if result is None:
            return

        is_correct = result["is_correct"]
        points_to_add = result["points_to_add"]
        got_speed_bonus = result["got_speed_bonus"]
        elapsed = result["elapsed"]

    if is_correct:
        add_points(user.id, points_to_add)
        record_correct_answer(user.id, answer_time=elapsed)

        if chat_id < 0:
            ensure_group_player(chat_id, user)
            add_group_points(chat_id, user, points_to_add)
            record_group_correct_answer(chat_id, user)

        display_name = f"@{user.username}" if user.username else user.full_name

        reward_text = f"✅ {display_name} +{base_points} 🍋"
        if got_speed_bonus:
            reward_text += f"\n⚡ Speed bonus +{speed_bonus_points}"

        msg = await context.bot.send_message(chat_id, reward_text)
        safe_task(delete_later(context, chat_id, msg.message_id, 4))
    else:
        record_wrong_answer(user.id)

        if chat_id < 0:
            ensure_group_player(chat_id, user)
            record_group_wrong_answer(chat_id, user)


async def delete_later(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    delay: int = 4,
):
    await asyncio.sleep(delay)
    await safe_delete_message(context.bot, chat_id, message_id)