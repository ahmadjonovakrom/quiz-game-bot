import time
import asyncio
import logging
from datetime import date

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
    list_questions,
    ensure_player,
    add_points,
    record_correct_answer,
    record_wrong_answer,
    increment_games_played,
    increment_games_won,
    create_game,
    finish_game,
    record_game_result,
)
from utils.helpers import (
    safe_task,
    safe_delete_message,
    build_join_text,
    clickable_name,
)

logger = logging.getLogger(__name__)

active_games = {}
poll_map = {}
daily_quiz_players = {}

ROUNDS_PER_GAME = 5


def get_unused_question(used_ids, category=None, difficulty=None):
    questions = list_questions(limit=500)

    filtered = []
    for q in questions:
        if q["id"] in used_ids:
            continue
        if not q["is_active"]:
            continue
        if category and q["category"] != category:
            continue
        if difficulty and q["difficulty"] != difficulty:
            continue
        filtered.append(q)

    if not filtered:
        return None

    import random
    return random.choice(filtered)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎮 Play Quiz", callback_data="menu_play")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("👤 My Profile", callback_data="menu_profile")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome to English Lemon 🍋!\n\n"
        "Practice vocabulary, play quiz games, and climb the leaderboard.",
        reply_markup=reply_markup,
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    back_keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]

    if data == "menu_play":
        await query.edit_message_text(
            "To start a quiz game, add me to a group and use:\n\n"
            "/startgame",
            reply_markup=InlineKeyboardMarkup(back_keyboard),
        )

    elif data == "menu_leaderboard":
        await query.edit_message_text(
            "Leaderboard options:\n\n"
            "/leaderboard - group ranking\n"
            "/global - global ranking",
            reply_markup=InlineKeyboardMarkup(back_keyboard),
        )

    elif data == "menu_profile":
        await query.edit_message_text(
            "Use /profile to see your stats.",
            reply_markup=InlineKeyboardMarkup(back_keyboard),
        )

    elif data == "menu_help":
        await query.edit_message_text(
            "English Lemon 🍋 Commands:\n\n"
            "/start - open the main menu\n"
            "/startgame - start a new game in a group\n"
            "/stopgame - stop the current game\n"
            "/dailyquiz - play one daily quiz\n"
            "/leaderboard - group leaderboard\n"
            "/global - global leaderboard\n"
            "/profile - your profile\n"
            "/questions - view saved questions",
            reply_markup=InlineKeyboardMarkup(back_keyboard),
        )

    elif data == "menu_back":
        keyboard = [
            [InlineKeyboardButton("🎮 Play Quiz", callback_data="menu_play")],
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
            [InlineKeyboardButton("👤 My Profile", callback_data="menu_profile")],
            [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
        ]

        await query.edit_message_text(
            "Welcome to English Lemon 🍋!\n\n"
            "Practice vocabulary, play quiz games, and climb the leaderboard.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(update.effective_user.id))


async def daily_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    today = str(date.today())

    if user.id in daily_quiz_players and daily_quiz_players[user.id] == today:
        await update.message.reply_text("You already played today’s daily quiz.")
        return

    ensure_player(user)

    question = get_random_question()
    if not question:
        await update.message.reply_text("No questions available.")
        return

    q_id = question["id"]
    q_text = question["question_text"]
    a = question["option_a"]
    b = question["option_b"]
    c = question["option_c"]
    d = question["option_d"]
    correct_index = question["correct_option"] - 1

    if correct_index not in (0, 1, 2, 3):
        await update.message.reply_text("This daily question has an invalid correct answer.")
        return

    msg = await context.bot.send_poll(
        chat_id=chat.id,
        question=f"📅 Daily Quiz\n\n{q_text}",
        options=[a, b, c, d],
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False,
        open_period=QUESTION_SECONDS,
    )

    poll_map[msg.poll.id] = {
        "chat_id": chat.id,
        "round": "daily",
        "daily_user_id": user.id,
        "daily_date": today,
        "correct_index": correct_index,
        "question_id": q_id,
    }

    daily_quiz_players[user.id] = today


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

    db_game_id = game.get("db_game_id")
    if db_game_id:
        try:
            finish_game(
                game_id=db_game_id,
                winner_user_id=None,
                total_players=len(game["players"]),
                total_rounds=game.get("round", 0),
                status="stopped",
            )
        except Exception:
            logger.exception("Failed to mark stopped game in database")

    active_games.pop(chat.id, None)
    await update.message.reply_text("Game stopped.")


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("Use /startgame in a group.")
        return

    game = active_games.get(chat.id)
    if game:
        if game["status"] == "joining":
            await update.message.reply_text("A game is already waiting for players.")
        elif game["status"] == "running":
            await update.message.reply_text("A game is already running.")
        else:
            await update.message.reply_text("A game already exists in this group.")
        return

    keyboard = [[InlineKeyboardButton("Join", callback_data=f"join|{chat.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await context.bot.send_message(
        chat_id=chat.id,
        text=build_join_text({"players": {}}, JOIN_SECONDS),
        reply_markup=reply_markup,
        parse_mode="HTML",
    )

    active_games[chat.id] = {
        "status": "joining",
        "started_by": user.id,
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
        "correct_counts": {},
        "wrong_counts": {},
        "answer_times": {},
        "db_game_id": None,
    }

    safe_task(begin_game_after_join(chat.id, context))


async def begin_game_after_join(chat_id, context):
    remaining = JOIN_SECONDS

    while remaining > 0:
        game = active_games.get(chat_id)
        if not game or game["status"] != "joining":
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
        except Exception as e:
            logger.warning("Failed to edit join message: %s", e)

        sleep_for = min(10, remaining)
        await asyncio.sleep(sleep_for)
        remaining -= sleep_for

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

    try:
        game["db_game_id"] = create_game(
            chat_id=chat_id,
            total_players=len(game["players"]),
            total_rounds=ROUNDS_PER_GAME,
            status="running",
        )
    except Exception:
        logger.exception("Failed to create game record")

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
    game["correct_counts"][user.id] = 0
    game["wrong_counts"][user.id] = 0
    game["answer_times"][user.id] = []

    ensure_player(user)

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
    except Exception as e:
        logger.warning("Failed to update join message after join: %s", e)

    await query.answer("Joined!")


async def send_question(chat_id, context):
    game = active_games.get(chat_id)
    if not game:
        return

    if game["status"] != "running":
        return

    game["round"] += 1

    if game["round"] > ROUNDS_PER_GAME:
        await end_game(chat_id, context)
        return

    question = get_unused_question(game["used_question_ids"])
    if not question:
        await context.bot.send_message(chat_id, "No more questions available. Ending game.")
        await end_game(chat_id, context)
        return

    q_id = question["id"]
    q_text = question["question_text"]
    a = question["option_a"]
    b = question["option_b"]
    c = question["option_c"]
    d = question["option_d"]
    correct_index = question["correct_option"] - 1

    if correct_index not in (0, 1, 2, 3):
        await context.bot.send_message(
            chat_id,
            f"Question ID {q_id} has an invalid correct option.",
        )
        await end_game(chat_id, context)
        return

    game["used_question_ids"].add(q_id)
    game["correct"] = correct_index
    game["answered"] = set()
    game["speed_bonus_awarded"] = {}

    msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"[{game['round']}/{ROUNDS_PER_GAME}] {q_text}",
        options=[a, b, c, d],
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False,
        open_period=QUESTION_SECONDS,
    )

    game["question_started_at"] = time.monotonic()
    game["current_poll_id"] = msg.poll.id
    poll_map[msg.poll.id] = {"chat_id": chat_id, "round": game["round"]}

    logger.info("Sent poll %s in chat %s for round %s", msg.poll.id, chat_id, game["round"])

    safe_task(wait_and_continue(chat_id, context, msg.poll.id, game["round"]))


async def wait_and_continue(chat_id, context, poll_id, round_number):
    try:
        logger.info(
            "wait_and_continue started: chat_id=%s poll_id=%s round=%s",
            chat_id, poll_id, round_number
        )

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

        if game.get("round") != round_number:
            poll_map.pop(poll_id, None)
            return

        poll_map.pop(poll_id, None)

        await asyncio.sleep(1)
        await send_question(chat_id, context)

    except Exception:
        logger.exception("Error in wait_and_continue")


async def delete_later(context, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    await safe_delete_message(context.bot, chat_id, message_id)


async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id

    info = poll_map.get(poll_id)
    if not info:
        return

    # Daily quiz
    if info.get("round") == "daily":
        user = answer.user
        ensure_player(user)

        if user.id != info.get("daily_user_id"):
            return

        if answer.option_ids and answer.option_ids[0] == info["correct_index"]:
            add_points(user.id, CORRECT_POINTS)
            record_correct_answer(user.id)

            msg = await context.bot.send_message(
                info["chat_id"],
                f"📅 Daily Quiz\n✅ {user.full_name} got it right!\n🍋 +{CORRECT_POINTS} points"
            )
            safe_task(delete_later(context, info["chat_id"], msg.message_id, 4))
        else:
            record_wrong_answer(user.id)

            msg = await context.bot.send_message(
                info["chat_id"],
                f"📅 Daily Quiz\n❌ {user.full_name} got it wrong."
            )
            safe_task(delete_later(context, info["chat_id"], msg.message_id, 4))

        poll_map.pop(poll_id, None)
        return

    # Normal game
    chat_id = info["chat_id"]
    game = active_games.get(chat_id)

    if not game:
        return

    user = answer.user
    ensure_player(user)

    if user.id not in game["players"]:
        return

    if user.id in game["answered"]:
        return

    game["answered"].add(user.id)

    is_correct = bool(answer.option_ids) and answer.option_ids[0] == game["correct"]

    if is_correct:
        points_to_add = CORRECT_POINTS
        got_speed_bonus = False
        elapsed = None

        started_at = game.get("question_started_at")
        if started_at is not None:
            elapsed = time.monotonic() - started_at
            game["answer_times"][user.id].append(elapsed)

            if elapsed <= SPEED_BONUS_SECONDS:
                points_to_add += SPEED_BONUS_POINTS
                got_speed_bonus = True
                game["speed_bonus_awarded"][user.id] = True
            else:
                game["speed_bonus_awarded"][user.id] = False

        game["scores"][user.id] += points_to_add
        game["correct_counts"][user.id] += 1

        add_points(user.id, points_to_add)
        record_correct_answer(user.id, answer_time=elapsed)

        reward_text = (
            f"🎯 {user.full_name}\n"
            f"🍋 +{CORRECT_POINTS} points"
        )

        if got_speed_bonus:
            reward_text += f"\n⚡ +{SPEED_BONUS_POINTS} speed bonus!"

        msg = await context.bot.send_message(chat_id, reward_text)
        safe_task(delete_later(context, chat_id, msg.message_id, 4))
    else:
        game["wrong_counts"][user.id] += 1
        record_wrong_answer(user.id)


async def end_game(chat_id, context):
    game = active_games.get(chat_id)
    if not game:
        return

    current_poll_id = game.get("current_poll_id")
    if current_poll_id:
        poll_map.pop(current_poll_id, None)

    ranking = sorted(
        game["scores"].items(),
        key=lambda x: x[1],
        reverse=True,
    )

    winner_user_id = ranking[0][0] if ranking else None

    for uid in game["players"].keys():
        try:
            increment_games_played(uid)
        except Exception:
            logger.exception("Failed to increment games_played for %s", uid)

    if winner_user_id is not None:
        try:
            increment_games_won(winner_user_id)
        except Exception:
            logger.exception("Failed to increment games_won for %s", winner_user_id)

    db_game_id = game.get("db_game_id")
    if db_game_id:
        try:
            position_map = {}
            for i, (uid, _) in enumerate(ranking, start=1):
                position_map[uid] = i

            for uid in game["players"].keys():
                answer_times = game["answer_times"].get(uid, [])
                avg_answer_time = (
                    sum(answer_times) / len(answer_times) if answer_times else None
                )

                record_game_result(
                    game_id=db_game_id,
                    user_id=uid,
                    score=game["scores"].get(uid, 0),
                    correct_count=game["correct_counts"].get(uid, 0),
                    wrong_count=game["wrong_counts"].get(uid, 0),
                    avg_answer_time=avg_answer_time,
                    position=position_map.get(uid),
                )

            finish_game(
                game_id=db_game_id,
                winner_user_id=winner_user_id,
                total_players=len(game["players"]),
                total_rounds=min(game["round"], ROUNDS_PER_GAME),
                status="finished",
            )
        except Exception:
            logger.exception("Failed to save game results")

    text = "🏆 Game Results\n\n"

    if not ranking:
        text += "No players scored any points."
    else:
        for i, (uid, pts) in enumerate(ranking, start=1):
            name = game["players"][uid]
            text += f"{i}. {name} — {pts} 🍋\n"

    await context.bot.send_message(chat_id, text, parse_mode="HTML")

    active_games.pop(chat_id, None)