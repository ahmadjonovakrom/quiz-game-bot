import asyncio
import html
import logging
from datetime import date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.shuffle import shuffle_question
from config import (
    CORRECT_POINTS,
    DEFAULT_QUESTIONS_PER_GAME,
    ALLOWED_QUESTION_COUNTS,
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
)
from database import (
    get_random_question,
    ensure_player,
    ensure_user,
    ensure_chat,
    ensure_group_player,
    add_points,
    add_group_points,
    record_correct_answer,
    record_group_correct_answer,
    record_group_wrong_answer,
    record_wrong_answer,
    increment_games_played,
    increment_group_games_played,
    increment_games_won,
    increment_group_games_won,
    create_game,
    finish_game,
    record_game_result,
    has_played_daily_quiz,
    record_daily_quiz_attempt,
    get_game_settings,
    has_claimed_group_bonus,
)
from handlers.profile import profile, leaderboard
from handlers.group_bonus import try_give_group_bonus
from utils.helpers import (
    safe_task,
    safe_delete_message,
    build_join_text,
    is_admin,
    is_group_admin,
    is_game_controller,
    is_running_game_controller,
)
from utils.keyboards import (
    main_menu_keyboard,
    game_setup_questions_keyboard,
    game_setup_categories_keyboard,
    game_setup_confirm_keyboard,
    final_results_keyboard,
    FINAL_RESULTS_PAGE_SIZE,
)
from services.game_service import (
    active_games,
    poll_map,
    get_game_lock,
    cleanup_game_lock,
    clear_game,
    create_new_game_data,
    get_existing_game_message,
    get_unused_question,
    add_player_to_game,
    mark_game_joining,
    start_next_round,
    prepare_round_state,
    apply_poll_answer,
)

logger = logging.getLogger(__name__)
from handlers.game_results import show_saved_results, end_game


def row_value(row, key, default=None):
    if row is None:
        return default
    try:
        value = row[key]
        return default if value is None else value
    except Exception:
        return default

from handlers.game_setup import (
    load_dynamic_settings,
    refresh_join_message,
    game_setup_callback_handler,
)

def get_question_points(difficulty: str) -> int:
    settings = load_dynamic_settings()
    points = settings["POINTS"]

    if not difficulty:
        return points["easy"]
    return points.get(str(difficulty).lower(), points["easy"])


def format_question_text(question: str, points: int) -> str:
    return f"{question}\n🍋 +{points}"


async def daily_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_dynamic_settings()
    question_seconds = settings["QUESTION_SECONDS"]

    logger.warning("DAILY QUIZ COMMAND RECEIVED")

    user = update.effective_user
    chat = update.effective_chat
    today = str(date.today())

    if chat:
        ensure_chat(chat)

    if has_played_daily_quiz(user.id, today):
        await update.message.reply_text("You already played today’s daily quiz.")
        return

    ensure_player(user)

    try:
        question = get_random_question()
        logger.warning("Daily question fetched: %s", dict(question) if question else None)
    except Exception:
        logger.exception("Failed to fetch daily question")
        await update.message.reply_text("❌ Failed to load daily question.")
        return

    if not question:
        await update.message.reply_text("No questions available.")
        return

    try:
        q_id = question["id"]
        q_text = question["question_text"]
        difficulty = row_value(question, "difficulty", "easy")
        points = get_question_points(difficulty)

        options, correct_index = shuffle_question(question)

        if correct_index not in (0, 1, 2, 3):
            await update.message.reply_text("This daily question has an invalid correct answer.")
            return

        msg = await context.bot.send_poll(
            chat_id=chat.id,
            question=format_question_text(q_text, points),
            options=options,
            type="quiz",
            correct_option_id=correct_index,
            is_anonymous=False,
            open_period=question_seconds,
        )
    except Exception:
        logger.exception("Failed to send daily quiz poll for user %s", user.id)
        await update.message.reply_text("Failed to send the daily quiz.\nPlease try again.")
        return

    poll_map[msg.poll.id] = {
        "chat_id": chat.id,
        "round": "daily",
        "daily_user_id": user.id,
        "daily_date": today,
        "correct_index": correct_index,
        "question_id": q_id,
        "difficulty": difficulty,
        "points": points,
    }

    record_daily_quiz_attempt(user.id, today)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.warning("BUTTON CALLBACK: %s", query.data)

    data = query.data

    if (
        data.startswith("setup_")
        or data in ("menu_back", "menu_main")
        or data.startswith("setup_back_to_results:")
    ):
        handled = await game_setup_callback_handler(update, context)
        if handled is True:
            return

    # Handle join button
    parts = data.split("|")
    if parts[0] == "join":
        await query.answer()

        try:
            chat_id = int(parts[1])
        except (IndexError, ValueError):
            await query.answer("Invalid join request.")
            return

        if query.message and query.message.chat:
            ensure_chat(query.message.chat)

        lock = get_game_lock(chat_id)

        async with lock:
            game = active_games.get(chat_id)

            if not game:
                await query.answer("No active game")
                return

            if game["status"] != "joining":
                await query.answer("Joining closed")
                return

            user = query.from_user
            added = add_player_to_game(game, user)

            if not added:
                await query.answer("Already joined")
                return

        ensure_player(user)

        if chat_id < 0:
            ensure_group_player(chat_id, user)

        await refresh_join_message(context, chat_id)
        await query.answer("Joined!")
        return

    await query.answer()

async def send_question(chat_id, context):
    settings = load_dynamic_settings()
    question_seconds = settings["QUESTION_SECONDS"]

    logger.warning("SEND QUESTION: %s", chat_id)

    should_end = False

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            return

        current_round, questions_per_game, should_end = start_next_round(game)

    if should_end:
        await end_game(chat_id, context)
        return

    lock = get_game_lock(chat_id)
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

    lock = get_game_lock(chat_id)
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


async def delete_later(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 4):
    await asyncio.sleep(delay)
    await safe_delete_message(context.bot, chat_id, message_id)
