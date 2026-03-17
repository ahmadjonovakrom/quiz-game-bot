import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    MIN_PLAYERS,
    JOIN_SECONDS,
    QUESTION_SECONDS,
    CORRECT_POINTS,
    SPEED_BONUS_SECONDS,
    SPEED_BONUS_POINTS,
)
from database import (
    get_random_question,
    ensure_player,
    add_points,
    record_correct_answer,
    record_game_played,
)
from utils.helpers import (
    safe_task,
    safe_delete_message,
    build_join_text,
    clickable_name,
)

active_games = {}
poll_map = {}

ROUNDS_PER_GAME = 5


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Quiz Game Bot is running!")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(update.effective_user.id))


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.id not in active_games:
        await update.message.reply_text("No game is currently running.")
        return

    game = active_games.get(chat.id)

    poll_id = game.get("current_poll_id")
    if poll_id:
        poll_map.pop(poll_id, None)

    await safe_delete_message(context.bot, chat.id, game.get("join_message_id"))

    active_games.pop(chat.id, None)
    await update.message.reply_text("Game stopped.")


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await update.message.reply_text("Use /startgame in a group.")
        return

    if chat.id in active_games:
        await update.message.reply_text("Game already running.")
        return

    keyboard = [[InlineKeyboardButton("Join", callback_data=f"join|{chat.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text(
    build_join_text({"players": {}}, JOIN_SECONDS),
    reply_markup=reply_markup,
    parse_mode="HTML",
)
    active_games[chat.id] = {
        "status": "joining",
        "players": {},
        "scores": {},
        "round": 0,
        "answered": set(),
        "current_poll_id": None,
        "correct": None,
        "join_message_id": msg.message_id,
        "used_question_ids": set(),
        "question_started_at": None,
        "speed_bonus_awarded": {},
    }

    safe_task(begin_game_after_join(chat.id, context))


async def begin_game_after_join(chat_id, context):
    steps = list(range(JOIN_SECONDS, 0, -10))

    for remaining in steps:
        game = active_games.get(chat_id)
        if not game:
            return

        if game["status"] != "joining":
            return

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game["join_message_id"],
                text=build_join_text(game, remaining),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Join", callback_data=f"join|{chat_id}")]]
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

        await asyncio.sleep(10)

    game = active_games.get(chat_id)
    if not game:
        return

    if len(game["players"]) < MIN_PLAYERS:
        await safe_delete_message(context.bot, chat_id, game.get("join_message_id"))

        await context.bot.send_message(
            chat_id,
            f"Not enough players to start the game.\n\nMinimum players needed: {MIN_PLAYERS}",
        )

        active_games.pop(chat_id, None)
        return

    game["status"] = "running"

    await safe_delete_message(context.bot, chat_id, game.get("join_message_id"))
    await context.bot.send_message(chat_id, "Game started! Get ready for the first question.")
    await send_question(chat_id, context)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("|")

    if data[0] != "join":
        await query.answer()
        return

    chat_id = int(data[1])
    game = active_games.get(chat_id)

    if not game:
        await query.answer("No active game")
        return

    if game["status"] != "joining":
        await query.answer("Joining closed")
        return

    user = query.from_user

    if user.id in game["players"]:
        await query.answer("Already joined")
        return

    name = clickable_name(user)

    game["players"][user.id] = name
    game["scores"][user.id] = 0

    ensure_player(user.id, user.username, user.full_name)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["join_message_id"],
            text=build_join_text(game, JOIN_SECONDS),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Join", callback_data=f"join|{chat_id}")]]
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await query.answer("Joined!")


async def send_question(chat_id, context):
    game = active_games.get(chat_id)
    if not game:
        return

    game["round"] += 1

    if game["round"] > ROUNDS_PER_GAME:
        await end_game(chat_id, context)
        return

    question = get_random_question(exclude_ids=list(game["used_question_ids"]))
    if not question:
        await context.bot.send_message(chat_id, "No more questions available. Ending game.")
        await end_game(chat_id, context)
        return

    q_id, q_text, a, b, c, d, correct = question
    game["used_question_ids"].add(q_id)

    options = [a, b, c, d]

    try:
        correct_index = ["A", "B", "C", "D"].index(correct.upper())
    except ValueError:
        await context.bot.send_message(
            chat_id,
            f"Question ID {q_id} has an invalid correct option."
        )
        await end_game(chat_id, context)
        return

    game["correct"] = correct_index
    game["answered"] = set()
    game["speed_bonus_awarded"] = {}

    msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"[{game['round']}/{ROUNDS_PER_GAME}] {q_text}",
        options=options,
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False,
        open_period=QUESTION_SECONDS,
    )

    game["question_started_at"] = time.monotonic()
    game["current_poll_id"] = msg.poll.id
    poll_map[msg.poll.id] = {"chat_id": chat_id, "round": game["round"]}

    safe_task(wait_and_continue(chat_id, context, msg.poll.id, game["round"]))


async def wait_and_continue(chat_id, context, poll_id, round_number):
    await asyncio.sleep(QUESTION_SECONDS + 2)

    game = active_games.get(chat_id)
    if not game:
        poll_map.pop(poll_id, None)
        return

    if game["status"] != "running":
        poll_map.pop(poll_id, None)
        return

    if game.get("current_poll_id") != poll_id:
        poll_map.pop(poll_id, None)
        return

    poll_map.pop(poll_id, None)

    await asyncio.sleep(1)
    await send_question(chat_id, context)


async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id

    info = poll_map.get(poll_id)
    if not info:
        return

    chat_id = info["chat_id"]
    game = active_games.get(chat_id)

    if not game:
        return

    user = answer.user

    if user.id not in game["players"]:
        return

    if user.id in game["answered"]:
        return

    game["answered"].add(user.id)

    if answer.option_ids and answer.option_ids[0] == game["correct"]:
        points_to_add = CORRECT_POINTS
        got_speed_bonus = False
        elapsed = None

        started_at = game.get("question_started_at")
        if started_at is not None:
            elapsed = time.monotonic() - started_at
            if elapsed <= SPEED_BONUS_SECONDS:
                points_to_add += SPEED_BONUS_POINTS
                got_speed_bonus = True
                game["speed_bonus_awarded"][user.id] = True
            else:
                game["speed_bonus_awarded"][user.id] = False

        game["scores"][user.id] += points_to_add

        add_points(
            user.id,
            user.username,
            user.full_name,
            chat_id,
            points_to_add,
        )

        record_correct_answer(user.id)

        if got_speed_bonus:
            await context.bot.send_message(
                chat_id,
                f"⚡ {user.full_name} got a speed bonus! +{SPEED_BONUS_POINTS} points"
            )
        elif elapsed is not None:
            await context.bot.send_message(
                chat_id,
                f"{user.full_name} answered correctly, but no speed bonus. Elapsed: {elapsed:.2f}s"
            )


async def end_game(chat_id, context):
    game = active_games.get(chat_id)
    if not game:
        return

    current_poll_id = game.get("current_poll_id")
    if current_poll_id:
        poll_map.pop(current_poll_id, None)

    record_game_played(list(game["players"].keys()))

    ranking = sorted(
        game["scores"].items(),
        key=lambda x: x[1],
        reverse=True,
    )

    text = "🏆 Game Results\n\n"

    if not ranking:
        text += "No players scored any points."
    else:
        for i, (uid, pts) in enumerate(ranking, start=1):
            name = game["players"][uid]
            text += f"{i}. {name} — {pts} 🍋\n"

    await context.bot.send_message(chat_id, text, parse_mode="HTML")

    active_games.pop(chat_id, None)