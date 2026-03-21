import asyncio
import logging
from datetime import date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.shuffle import shuffle_question
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
    POINTS,
)
from database import (
    get_random_question,
    ensure_player,
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
)
from handlers.profile import profile, leaderboard
from utils.helpers import (
    safe_task,
    safe_delete_message,
    build_join_text,
    is_admin,
)
from utils.keyboards import (
    main_menu_keyboard,
    game_setup_questions_keyboard,
    game_setup_categories_keyboard,
    game_setup_confirm_keyboard,
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
    get_join_remaining_seconds,
    add_player_to_game,
    mark_game_joining,
    start_next_round,
    prepare_round_state,
    apply_poll_answer,
    build_final_results,
    build_results_text,
)

logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "mixed": "Mixed",
    "vocabulary": "Vocabulary",
    "grammar": "Grammar",
    "idioms_phrases": "Idioms & Phrases",
    "synonyms": "Synonyms",
    "collocations": "Collocations",
}


def format_category_name(category: str) -> str:
    return CATEGORY_LABELS.get(str(category).lower(), str(category).replace("_", " ").title())


def get_main_menu_keyboard():
    return main_menu_keyboard()


def get_question_count_keyboard():
    return game_setup_questions_keyboard()


def get_category_keyboard():
    return game_setup_categories_keyboard()


def get_setup_confirmation_keyboard():
    return game_setup_confirm_keyboard()


def get_join_keyboard(chat_id: int):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Join", callback_data=f"join|{chat_id}")]]
    )


def format_setup_step_1_text() -> str:
    return (
        "🎮 Game Setup\n\n"
        "Step 1 of 2 — Choose number of questions"
    )


def format_setup_step_2_text(selected_count: int) -> str:
    return (
        "🎮 Game Setup\n\n"
        "Step 2 of 2 — Choose category\n\n"
        f"✅ Questions: {selected_count}"
    )


def format_setup_summary(question_count: int, category: str) -> str:
    return (
        "🎮 Game Setup\n\n"
        "✅ Ready to Start\n\n"
        "📋 Setup:\n"
        f"• Questions: {question_count}\n"
        f"• Category: {format_category_name(category)}\n"
        "• Difficulty: Mixed\n\n"
        "🍋 Rewards:\n"
        f"• Easy: +{POINTS['easy']}\n"
        f"• Medium: +{POINTS['medium']}\n"
        f"• Hard: +{POINTS['hard']}\n\n"
        "🚀 Press Start when you're ready"
    )


def get_question_points(difficulty: str) -> int:
    if not difficulty:
        return POINTS["easy"]
    return POINTS.get(str(difficulty).lower(), POINTS["easy"])


def format_question_text(question: str, points: int) -> str:
    return f"{question}\n🍋 +{points}"


async def refresh_join_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = active_games.get(chat_id)
    if not game or game.get("status") != "joining":
        return

    join_message_id = game.get("join_message_id")
    if not join_message_id:
        return

    remaining = get_join_remaining_seconds(game)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=join_message_id,
            text=build_join_text(game, remaining),
            reply_markup=get_join_keyboard(chat_id),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Failed to refresh join message in chat %s: %s", chat_id, e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("START COMMAND RECEIVED")

    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if user:
        ensure_player(user)
    if chat:
        ensure_chat(chat)

    await message.reply_text(
        "Welcome to English Lemon !\n\n"
        "Practice vocabulary, play quiz games, and climb the leaderboard.",
        reply_markup=get_main_menu_keyboard(),
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.warning("MENU CALLBACK: %s", query.data)
    await query.answer()

    data = query.data
    back_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
    )

    if data == "menu_play":
        if query.message.chat.type in ("group", "supergroup"):
            if not is_admin(query.from_user.id):
                await query.edit_message_text(
                    "❌ Admin only.\n\nOnly a group admin can start a quiz game.",
                    reply_markup=back_kb,
                )
                return
            await start_game(update, context)
            return
        else:
            await query.edit_message_text(
                "To start a quiz game, add me to a group and use:\n\n/startgame",
                reply_markup=back_kb,
            )
            return

    if data == "menu_leaderboard":
        await leaderboard(update, context)
        return

    if data == "menu_profile":
        await profile(update, context)
        return

    if data == "menu_help":
        await query.edit_message_text(
            "English Lemon Commands:\n\n"
            "/start - open the main menu\n"
            "/startgame - start a new game in a group\n"
            "/stopgame - stop the current game\n"
            "/dailyquiz - play one daily quiz\n"
            "/leaderboard - leaderboard\n"
            "/daily - today's leaderboard\n"
            "/weekly - this week's leaderboard\n"
            "/monthly - this month's leaderboard\n"
            "/profile - your profile",
            reply_markup=back_kb,
        )
        return

    if data in ("menu_back", "menu_main"):
        chat_id = query.message.chat.id
        await clear_game(context, chat_id)
        await query.edit_message_text(
            "Welcome to English Lemon !\n\n"
            "Practice vocabulary, play quiz games, and climb the leaderboard.",
            reply_markup=get_main_menu_keyboard(),
        )
        return


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(update.effective_user.id))


async def daily_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    question = get_random_question()
    if not question:
        await update.message.reply_text("No questions available.")
        return

    q_id = question["id"]
    q_text = question["question_text"]
    difficulty = question.get("difficulty", "easy")
    points = get_question_points(difficulty)

    options, correct_index = shuffle_question(question)

    if correct_index not in (0, 1, 2, 3):
        await update.message.reply_text("This daily question has an invalid correct answer.")
        return

    try:
        msg = await context.bot.send_poll(
            chat_id=chat.id,
            question=format_question_text(q_text, points),
            options=options,
            type="quiz",
            correct_option_id=correct_index,
            is_anonymous=False,
            open_period=QUESTION_SECONDS,
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


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("START GAME COMMAND RECEIVED")

    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    query = update.callback_query

    if chat:
        ensure_chat(chat)

    if not user or not is_admin(user.id):
        if query:
            await query.edit_message_text("❌ Admin only.")
        else:
            await message.reply_text("❌ Admin only.")
        return

    if chat.type == "private":
        if query:
            await query.edit_message_text("Use /startgame in a group.")
        else:
            await message.reply_text("Use /startgame in a group.")
        return

    lock = get_game_lock(chat.id)
    async with lock:
        game = active_games.get(chat.id)
        if game:
            text = get_existing_game_message(game)
            if query:
                await query.answer(text, show_alert=True)
            else:
                await message.reply_text(text)
            return

        game = create_new_game_data(
            started_by=user.id,
            questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
            category=DEFAULT_CATEGORY,
            difficulty="mixed",
        )

        add_player_to_game(game, user)
        active_games[chat.id] = game

    text = format_setup_step_1_text()
    keyboard = get_question_count_keyboard()

    if query:
        await query.edit_message_text(text, reply_markup=keyboard)
    else:
        await message.reply_text(text, reply_markup=keyboard)


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("STOP GAME COMMAND RECEIVED")

    chat = update.effective_chat
    user = update.effective_user

    if not user or not is_admin(user.id):
        await update.message.reply_text("Admin only.")
        return

    lock = get_game_lock(chat.id)
    async with lock:
        if chat.id not in active_games:
            await update.message.reply_text("No game is currently running.")
            return

        game = active_games.get(chat.id)
        poll_id = game.get("current_poll_id")
        join_message_id = game.get("join_message_id")
        db_game_id = game.get("db_game_id")
        total_players = len(game.get("players", {}))
        total_rounds = game.get("round", 0)

        if poll_id:
            poll_map.pop(poll_id, None)

        active_games.pop(chat.id, None)
        cleanup_game_lock(chat.id)

    await safe_delete_message(context.bot, chat.id, join_message_id)

    if db_game_id:
        try:
            finish_game(
                game_id=db_game_id,
                winner_user_id=None,
                total_players=total_players,
                total_rounds=total_rounds,
                status="stopped",
            )
        except Exception:
            logger.exception("Failed to mark stopped game in database for chat %s", chat.id)

    await update.message.reply_text("Game stopped.")


async def game_setup_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.warning("SETUP CALLBACK: %s", query.data)

    data = query.data

    if not data.startswith("setup_") and data not in ("menu_back", "menu_main"):
        return False

    await query.answer()

    user = query.from_user
    chat_id = query.message.chat.id

    if data in ("menu_back", "menu_main"):
        await clear_game(context, chat_id)
        await query.edit_message_text(
            "Welcome to English Lemon !\n\n"
            "Practice vocabulary, play quiz games, and climb the leaderboard.",
            reply_markup=get_main_menu_keyboard(),
        )
        return True

    if not is_admin(user.id):
        await query.answer("Admin only.", show_alert=True)
        return True

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game:
            await query.edit_message_text("No active game setup found.")
            return True

        if game["status"] != "setup":
            await query.answer("Setup is closed.", show_alert=True)
            return True

        if data.startswith("setup_questions_"):
            try:
                count = int(data.split("_")[-1])
            except ValueError:
                await query.answer("Invalid question count.", show_alert=True)
                return True

            if count not in ALLOWED_QUESTION_COUNTS:
                await query.answer("Invalid question count.", show_alert=True)
                return True

            game["questions_per_game"] = count

            await query.edit_message_text(
                format_setup_step_2_text(count),
                reply_markup=get_category_keyboard(),
            )
            return True

        if data == "setup_back_to_questions":
            await query.edit_message_text(
                format_setup_step_1_text(),
                reply_markup=get_question_count_keyboard(),
            )
            return True

        if data.startswith("setup_category_"):
            category = data.replace("setup_category_", "", 1)

            if category not in ALLOWED_CATEGORIES:
                await query.answer("Invalid category.", show_alert=True)
                return True

            game["category"] = category
            game["difficulty"] = "mixed"

            await query.edit_message_text(
                format_setup_summary(
                    question_count=game["questions_per_game"],
                    category=game["category"],
                ),
                reply_markup=get_setup_confirmation_keyboard(),
            )
            return True

        if data == "setup_back_to_categories":
            await query.edit_message_text(
                format_setup_step_2_text(game["questions_per_game"]),
                reply_markup=get_category_keyboard(),
            )
            return True

        if data == "setup_start_game":
            mark_game_joining(game, JOIN_SECONDS)

            await query.edit_message_text(
                text=build_join_text(game, JOIN_SECONDS),
                reply_markup=get_join_keyboard(chat_id),
                parse_mode="HTML",
            )

            game["join_message_id"] = query.message.message_id

            safe_task(begin_game_after_join(chat_id, context))
            return True

    return False


async def begin_game_after_join(chat_id, context):
    logger.warning("BEGIN GAME AFTER JOIN: %s", chat_id)

    try:
        while True:
            lock = get_game_lock(chat_id)
            async with lock:
                game = active_games.get(chat_id)
                if not game or game["status"] != "joining":
                    return

                remaining = get_join_remaining_seconds(game)
                if remaining <= 0:
                    break

            await refresh_join_message(context, chat_id)
            await asyncio.sleep(min(10, max(1, remaining)))

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if not game or game["status"] != "joining":
                return

            join_message_id = game.get("join_message_id")

            if len(game["players"]) < MIN_PLAYERS:
                active_games.pop(chat_id, None)
                cleanup_game_lock(chat_id)
                not_enough_players = True
            else:
                game["status"] = "running"
                not_enough_players = False

        await safe_delete_message(context.bot, chat_id, join_message_id)

        if not_enough_players:
            await context.bot.send_message(
                chat_id,
                f"❌ Not enough players.\nGame cancelled.\n\nMinimum players needed: {MIN_PLAYERS}",
            )
            return

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if not game or game["status"] != "running":
                return

            try:
                game["db_game_id"] = create_game(
                    chat_id=chat_id,
                    total_players=len(game["players"]),
                    total_rounds=game["questions_per_game"],
                    status="running",
                )
            except Exception:
                logger.exception("Failed to create game record for chat %s", chat_id)

        await context.bot.send_message(chat_id, "Game started! Get ready for the first question.")
        await send_question(chat_id, context)
    except Exception:
        logger.exception("Error in begin_game_after_join for chat %s", chat_id)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.warning("BUTTON CALLBACK: %s", query.data)

    data = query.data

    if data.startswith("setup_") or data in ("menu_back", "menu_main"):
        handled = await game_setup_callback_handler(update, context)
        if handled is True:
            return

    parts = data.split("|")
    if parts[0] != "join":
        await query.answer()
        return

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
        logger.warning("JOIN RESULT: user=%s added=%s total=%s", user.id, added, len(game["players"]))

        if not added:
            await query.answer("Already joined")
            return

    ensure_player(user)
    if chat_id < 0:
        ensure_group_player(chat_id, user)

    await refresh_join_message(context, chat_id)
    await query.answer("Joined!")


async def send_question(chat_id, context):
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

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            return

        question = get_unused_question(game)
        no_question = not question

    if no_question:
        await context.bot.send_message(
            chat_id,
            "No more unused questions available for this category/difficulty.\nEnding game.",
        )
        await end_game(chat_id, context)
        return

    q_id = question["id"]
    q_text = question["question_text"]
    difficulty = question.get("difficulty", "easy")
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

    try:
        msg = await context.bot.send_poll(
            chat_id=chat_id,
            question=poll_question,
            options=options,
            type="quiz",
            correct_option_id=correct_index,
            is_anonymous=False,
            open_period=QUESTION_SECONDS,
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
    await asyncio.sleep(QUESTION_SECONDS + 1)

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

        base_points = info.get("points", POINTS["easy"])

        result = apply_poll_answer(
            game=game,
            user_id=user.id,
            option_ids=answer.option_ids,
            correct_points=base_points,
            speed_bonus_seconds=SPEED_BONUS_SECONDS,
            speed_bonus_points=SPEED_BONUS_POINTS,
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
            reward_text += f"\n⚡ Speed bonus +{SPEED_BONUS_POINTS}"

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


async def end_game(chat_id, context):
    logger.warning("END GAME: %s", chat_id)

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game:
            return

        poll_id = game.get("current_poll_id")
        db_game_id = game.get("db_game_id")
        players = game.get("players", {})
        total_rounds = game.get("round", 0)
        scores = game.get("scores", {})
        correct_counts = game.get("correct_counts", {})
        wrong_counts = game.get("wrong_counts", {})

        if poll_id:
            poll_map.pop(poll_id, None)

        final_results = build_final_results(game)
        results_text = build_results_text(final_results)

        winner_user_id = None
        if final_results:
            winner_user_id = final_results[0].get("user_id")

        active_games.pop(chat_id, None)
        cleanup_game_lock(chat_id)

    try:
        if db_game_id:
            finish_game(
                game_id=db_game_id,
                winner_user_id=winner_user_id,
                total_players=len(players),
                total_rounds=total_rounds,
                status="finished",
            )
    except Exception:
        logger.exception("Failed to finish game for chat %s", chat_id)

    try:
        for user_id in players.keys():
            increment_games_played(user_id)
            if chat_id < 0:
                increment_group_games_played(chat_id, user_id)

            score = scores.get(user_id, 0)
            correct = correct_counts.get(user_id, 0)
            wrong = wrong_counts.get(user_id, 0)

            record_game_result(
                user_id=user_id,
                chat_id=chat_id,
                score=score,
                correct_answers=correct,
                wrong_answers=wrong,
                is_winner=(user_id == winner_user_id),
            )

        if winner_user_id:
            increment_games_won(winner_user_id)
            if chat_id < 0:
                increment_group_games_won(chat_id, winner_user_id)
    except Exception:
        logger.exception("Failed to save final game stats for chat %s", chat_id)

    await context.bot.send_message(
        chat_id,
        results_text if results_text else "🏁 Game finished.",
        parse_mode="HTML",
    )