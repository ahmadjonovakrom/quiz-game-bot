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
    DEFAULT_QUESTIONS_PER_GAME,
    ALLOWED_QUESTION_COUNTS,
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    DEFAULT_DIFFICULTY,
    ALLOWED_DIFFICULTIES,
)
from database import (
    get_random_question,
    ensure_player,
    ensure_chat,
    add_points,
    add_group_points,
    record_correct_answer,
    record_group_correct_answer,
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
)
from handlers.profile import profile, send_leaderboard_menu
from utils.helpers import (
    safe_task,
    safe_delete_message,
    build_join_text,
    clickable_name,
    is_admin,
    format_category_name,
)

logger = logging.getLogger(__name__)

active_games = {}
poll_map = {}
daily_quiz_players = {}


def format_difficulty_name(value: str) -> str:
    mapping = {
        "easy": "🟢 Easy",
        "medium": "🟡 Medium",
        "hard": "🔴 Hard",
    }
    return mapping.get(value, value.title())


def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎮 Play Quiz", callback_data="menu_play")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("👤 My Profile", callback_data="menu_profile")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_question_count_keyboard():
    rows = []
    row = []

    for count in ALLOWED_QUESTION_COUNTS:
        row.append(
            InlineKeyboardButton(
                f"{count} Questions",
                callback_data=f"setup_questions_{count}"
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def get_category_keyboard():
    rows = []

    for category in ALLOWED_CATEGORIES:
        rows.append([
            InlineKeyboardButton(
                format_category_name(category),
                callback_data=f"setup_category_{category}"
            )
        ])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def get_difficulty_keyboard():
    rows = []

    for difficulty in ALLOWED_DIFFICULTIES:
        rows.append([
            InlineKeyboardButton(
                format_difficulty_name(difficulty),
                callback_data=f"setup_difficulty_{difficulty}"
            )
        ])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def get_join_keyboard(chat_id: int):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Join", callback_data=f"join|{chat_id}")]]
    )


def get_unused_question(game):
    exclude_ids = list(game["used_question_ids"])

    return get_random_question(
        exclude_ids=exclude_ids,
        category=game.get("category"),
        difficulty=game.get("difficulty"),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if user:
        ensure_player(user)

    if chat:
        ensure_chat(chat)

    await message.reply_text(
        "Welcome to English Lemon 🍋!\n\n"
        "Practice vocabulary, play quiz games, and climb the leaderboard.",
        reply_markup=get_main_menu_keyboard(),
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    back_keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]

    if data == "menu_play":
        if query.message.chat.type in ("group", "supergroup"):
            await start_game(update, context)
        else:
            await query.edit_message_text(
                "To start a quiz game, add me to a group and use:\n\n"
                "/startgame",
                reply_markup=InlineKeyboardMarkup(back_keyboard),
            )
        return

    elif data == "menu_leaderboard":
        await send_leaderboard_menu(query)
        return

    elif data == "menu_profile":
        await profile(update, context)
        return

    elif data == "menu_help":
        await query.edit_message_text(
            "English Lemon 🍋 Commands:\n\n"
            "/start - open the main menu\n"
            "/startgame - start a new game in a group\n"
            "/stopgame - stop the current game\n"
            "/dailyquiz - play one daily quiz\n"
            "/leaderboard - leaderboard\n"
            "/global - global leaderboard\n"
            "/profile - your profile\n"
            "/questions - view saved questions",
            reply_markup=InlineKeyboardMarkup(back_keyboard),
        )
        return

    elif data == "menu_back" or data == "menu_main":
        await query.edit_message_text(
            "Welcome to English Lemon 🍋!\n\n"
            "Practice vocabulary, play quiz games, and climb the leaderboard.",
            reply_markup=get_main_menu_keyboard(),
        )
        return


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(update.effective_user.id))


async def daily_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    today = str(date.today())

    if chat:
        ensure_chat(chat)

    if has_played_daily_quiz(user.id, today):
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

    record_daily_quiz_attempt(user.id, today)


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    query = update.callback_query

    if chat:
        ensure_chat(chat)

    if not user or not is_admin(user.id):
        if query:
            await query.answer("Admin only.", show_alert=True)
        else:
            await message.reply_text("Admin only.")
        return

    if chat.type == "private":
        if query:
            await query.edit_message_text("Use /startgame in a group.")
        else:
            await message.reply_text("Use /startgame in a group.")
        return

    game = active_games.get(chat.id)
    if game:
        if game["status"] == "setup":
            text = "Game setup is already in progress."
        elif game["status"] == "joining":
            text = "A game is already waiting for players."
        elif game["status"] == "running":
            text = "A game is already running."
        else:
            text = "A game already exists in this group."

        if query:
            await query.answer(text, show_alert=True)
        else:
            await message.reply_text(text)
        return

    active_games[chat.id] = {
        "status": "setup",
        "started_by": user.id,
        "players": {},
        "player_objects": {},
        "scores": {},
        "round": 0,
        "answered": set(),
        "current_poll_id": None,
        "correct": None,
        "join_message_id": None,
        "used_question_ids": set(),
        "question_started_at": None,
        "speed_bonus_awarded": {},
        "correct_counts": {},
        "wrong_counts": {},
        "answer_times": {},
        "db_game_id": None,
        "questions_per_game": DEFAULT_QUESTIONS_PER_GAME,
        "category": DEFAULT_CATEGORY,
        "difficulty": DEFAULT_DIFFICULTY,
    }

    if query:
        await query.edit_message_text(
            "🎮 Game Setup\n\nChoose number of questions:",
            reply_markup=get_question_count_keyboard(),
        )
    else:
        await message.reply_text(
            "🎮 Game Setup\n\nChoose number of questions:",
            reply_markup=get_question_count_keyboard(),
        )


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not user or not is_admin(user.id):
        await update.message.reply_text("Admin only.")
        return

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


async def game_setup_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    chat_id = query.message.chat.id
    data = query.data

    if not is_admin(user.id):
        await query.answer("Admin only.", show_alert=True)
        return

    game = active_games.get(chat_id)
    if not game:
        await query.edit_message_text("No active game setup found.")
        return

    if game["status"] != "setup":
        await query.answer("Setup is closed.", show_alert=True)
        return

    if data.startswith("setup_questions_"):
        try:
            count = int(data.split("_")[-1])
        except ValueError:
            await query.answer("Invalid question count.", show_alert=True)
            return

        if count not in ALLOWED_QUESTION_COUNTS:
            await query.answer("Invalid question count.", show_alert=True)
            return

        game["questions_per_game"] = count

        await query.edit_message_text(
            f"🎮 Game Setup\n\n"
            f"✅ Questions: {count}\n\n"
            f"Now choose category:",
            reply_markup=get_category_keyboard(),
        )
        return

    if data.startswith("setup_category_"):
        category = data.replace("setup_category_", "", 1)

        if category not in ALLOWED_CATEGORIES:
            await query.answer("Invalid category.", show_alert=True)
            return

        game["category"] = category

        await query.edit_message_text(
            f"🎮 Game Setup\n\n"
            f"✅ Questions: {game['questions_per_game']}\n"
            f"✅ Category: {format_category_name(category)}\n\n"
            f"Now choose difficulty:",
            reply_markup=get_difficulty_keyboard(),
        )
        return

    if data.startswith("setup_difficulty_"):
        difficulty = data.replace("setup_difficulty_", "", 1)

        if difficulty not in ALLOWED_DIFFICULTIES:
            await query.answer("Invalid difficulty.", show_alert=True)
            return

        game["difficulty"] = difficulty

        keyboard = get_join_keyboard(chat_id)

        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=build_join_text(game, JOIN_SECONDS),
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        game["status"] = "joining"
        game["join_message_id"] = msg.message_id

        await query.edit_message_text(
            "✅ Game created.\n\n"
            f"📚 Questions: {game['questions_per_game']}\n"
            f"🗂 Category: {format_category_name(game['category'])}\n"
            f"🎯 Difficulty: {format_difficulty_name(game['difficulty'])}\n\n"
            "Players can join now."
        )

        safe_task(begin_game_after_join(chat_id, context))
        return


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
                reply_markup=get_join_keyboard(chat_id),
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
            f"❌ Not enough players.\nGame cancelled.\n\nMinimum players needed: {MIN_PLAYERS}",
        )

        active_games.pop(chat_id, None)
        return

    game["status"] = "running"

    try:
        game["db_game_id"] = create_game(
            chat_id=chat_id,
            total_players=len(game["players"]),
            total_rounds=game["questions_per_game"],
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

    if query.message and query.message.chat:
        ensure_chat(query.message.chat)

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
    game["player_objects"][user.id] = user
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
            reply_markup=get_join_keyboard(chat_id),
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

    if game["round"] > game["questions_per_game"]:
        await end_game(chat_id, context)
        return

    question = get_unused_question(game)

    if not question:
        await context.bot.send_message(
            chat_id,
            "No more unused questions available for this category/difficulty. Ending game."
        )
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
        question=f"[{game['round']}/{game['questions_per_game']}] {q_text}",
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

    if info.get("round") == "daily":
        user = answer.user
        ensure_player(user)

        if user.id != info.get("daily_user_id"):
            return

        if answer.option_ids and answer.option_ids[0] == info["correct_index"]:
            add_points(user.id, CORRECT_POINTS)
            record_correct_answer(user.id)

            display_name = f"@{user.username}" if user.username else user.full_name
            msg = await context.bot.send_message(
                info["chat_id"],
                f"✅ {display_name} +{CORRECT_POINTS} 🍋"
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

        if chat_id < 0:
            add_group_points(chat_id, user, points_to_add)
            record_group_correct_answer(chat_id, user)

        display_name = f"@{user.username}" if user.username else user.full_name
        reward_text = f"✅ {display_name} +{CORRECT_POINTS} 🍋"
        if got_speed_bonus:
            reward_text += f"\n⚡ Speed bonus +{SPEED_BONUS_POINTS} 🍋‍🟩"

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

        try:
            if chat_id < 0:
                player_user = game["player_objects"].get(uid)
                if player_user:
                    increment_group_games_played(chat_id, player_user)
        except Exception:
            logger.exception("Failed to increment group games_played for %s", uid)

    if winner_user_id is not None:
        try:
            increment_games_won(winner_user_id)
        except Exception:
            logger.exception("Failed to increment games_won for %s", winner_user_id)

        try:
            if chat_id < 0:
                winner_user = game["player_objects"].get(winner_user_id)
                if winner_user:
                    increment_group_games_won(chat_id, winner_user)
        except Exception:
            logger.exception("Failed to increment group games_won for %s", winner_user_id)

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
                total_rounds=min(game["round"], game["questions_per_game"]),
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