import logging
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

from utils.shuffle import shuffle_question
from config import (
    DEFAULT_QUESTIONS_PER_GAME,
    DEFAULT_CATEGORY,
)
from database import (
    get_random_question,
    ensure_player,
    ensure_chat,
    ensure_group_player,
    has_played_daily_quiz,
    record_daily_quiz_attempt,
)
from utils.helpers import safe_delete_message
from utils.keyboards import game_setup_questions_keyboard
from services.game_service import (
    active_games,
    poll_map,
    get_game_lock,
    clear_game,
    create_new_game_data,
    get_existing_game_message,
    add_player_to_game,
)
from handlers.game_setup import (
    load_dynamic_settings,
    refresh_join_message,
    game_setup_callback_handler,
    has_active_game,
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


def get_question_points(difficulty: str) -> int:
    settings = load_dynamic_settings()
    points = settings["POINTS"]

    if not difficulty:
        return points["easy"]

    return points.get(str(difficulty).lower(), points["easy"])


def format_question_text(question: str, points: int) -> str:
    return f"{question}\n🍋 +{points}"


async def _send_play_again_setup_message(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Send a fresh setup message after pressing Play Again.
    The old results message stays in chat.
    """
    return await context.bot.send_message(
        chat_id=chat_id,
        text="🎮 Game Setup\n\nStep 1 of 2 — Choose number of questions",
        reply_markup=game_setup_questions_keyboard(),
    )


async def daily_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_dynamic_settings()
    question_seconds = settings["QUESTION_SECONDS"]

    logger.warning("DAILY QUIZ COMMAND RECEIVED")

    user = update.effective_user
    chat = update.effective_chat
    today = str(date.today())

    if not update.message or not user or not chat:
        return

    ensure_chat(chat)

    if has_played_daily_quiz(user.id, today):
        await update.message.reply_text("You already played today’s daily quiz.")
        return

    ensure_player(user)

    try:
        question = get_random_question()
        logger.warning(
            "Daily question fetched: %s",
            dict(question) if question else None,
        )
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
            await update.message.reply_text(
                "This daily question has an invalid correct answer."
            )
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
        await update.message.reply_text(
            "Failed to send the daily quiz.\nPlease try again."
        )
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
    if not query or not query.message:
        return

    logger.warning("BUTTON CALLBACK: %s", query.data)
    data = query.data or ""

    if (
        data.startswith("setup_")
        or data in ("menu_back", "menu_main")
        or data.startswith("setup_back_to_results:")
    ):
        handled = await game_setup_callback_handler(update, context)
        if handled is True:
            return

    if data.startswith("results_play_again:"):
        chat_id = query.message.chat.id
        user = query.from_user

        try:
            int(data.split(":")[1])  # validate callback format
        except (IndexError, ValueError):
            await query.answer("Invalid game.", show_alert=True)
            return

        await query.answer()

        lock = get_game_lock(chat_id)
        async with lock:
            if has_active_game(chat_id):
                existing_game = active_games.get(chat_id)
                await query.answer(
                    get_existing_game_message(existing_game),
                    show_alert=True,
                )
                return

            old_game = active_games.get(chat_id)
            old_setup_message_id = None
            old_join_message_id = None

            if old_game:
                old_setup_message_id = old_game.get("setup_message_id")
                old_join_message_id = old_game.get("join_message_id")

            await clear_game(context, chat_id)

            game = create_new_game_data(
                started_by=user.id,
                questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
                category=DEFAULT_CATEGORY,
                difficulty="mixed",
            )
            game["chat_id"] = chat_id
            add_player_to_game(game, user)
            game["results_message_id"] = query.message.message_id
            game["setup_message_id"] = None
            game["join_message_id"] = None

            active_games[chat_id] = game

        if old_setup_message_id:
            await safe_delete_message(
                context.bot,
                chat_id,
                old_setup_message_id,
            )

        if old_join_message_id and old_join_message_id != old_setup_message_id:
            await safe_delete_message(
                context.bot,
                chat_id,
                old_join_message_id,
            )

        setup_message = await _send_play_again_setup_message(chat_id, context)

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if game:
                game["setup_message_id"] = setup_message.message_id

        return

    parts = data.split("|")
    if parts[0] == "join":
        await query.answer()

        try:
            chat_id = int(parts[1])
        except (IndexError, ValueError):
            await query.answer("Invalid join request.")
            return

        if query.message.chat:
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