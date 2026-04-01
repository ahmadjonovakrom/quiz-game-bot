import asyncio
import logging
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    DEFAULT_QUESTIONS_PER_GAME,
    DEFAULT_CATEGORY,
    ALLOWED_QUESTION_COUNTS,
    ALLOWED_CATEGORIES,
)
from database import (
    ensure_chat,
    create_game,
    get_game_settings,
)
from utils.helpers import (
    safe_task,
    safe_delete_message,
    build_join_text,
    is_game_controller,
)
from utils.keyboards import (
    game_setup_questions_keyboard,
    game_setup_categories_keyboard,
    game_setup_confirm_keyboard,
    main_menu_keyboard,
)
from services.game_service import (
    active_games,
    get_game_lock,
    cleanup_game_lock,
    clear_game,
    create_new_game_data,
    get_existing_game_message,
    add_player_to_game,
    mark_game_joining,
    get_join_remaining_seconds,
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

POSTPONE_SECONDS = 30
MAX_POSTPONES = 2


def load_dynamic_settings():
    settings = get_game_settings()
    return {
        "MIN_PLAYERS": settings["min_players"],
        "JOIN_SECONDS": settings["join_seconds"],
        "QUESTION_SECONDS": settings["question_seconds"],
        "SPEED_BONUS_SECONDS": settings["speed_bonus_seconds"],
        "SPEED_BONUS_POINTS": settings["speed_bonus_points"],
        "POINTS": settings["points"],
    }


def has_active_game(chat_id: int) -> bool:
    game = active_games.get(chat_id)
    if not game:
        return False
    return game.get("status") in ("setup", "joining", "running")


def format_category_name(category: str) -> str:
    return CATEGORY_LABELS.get(
        str(category).lower(),
        str(category).replace("_", " ").title(),
    )


def get_question_count_keyboard(back_callback: str = "menu_main"):
    return game_setup_questions_keyboard(back_callback)


def get_category_keyboard():
    return game_setup_categories_keyboard()


def get_setup_confirmation_keyboard():
    return game_setup_confirm_keyboard()


def get_join_keyboard(chat_id: int, mode: str = "solo"):
    text = "⚔️ Join Duel" if mode == "duel" else "✅Join"

    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(text, callback_data=f"join|{chat_id}")]]
    )


def format_setup_step_1_text(mode: str = "solo") -> str:
    if mode == "duel":
        return (
            "⚔️ Duel Setup\n\n"
            "Step 1 of 1 — Choose number of questions\n\n"
            "• Mode: 1 vs 1\n"
            "• Category: Mixed\n"
            "• Difficulty: Mixed"
        )

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


def format_setup_summary(question_count: int, category: str, mode: str = "solo") -> str:
    settings = load_dynamic_settings()
    points = settings["POINTS"]

    if mode == "duel":
        return (
            "⚔️ Duel Setup\n\n"
            "✅ Ready to Start\n\n"
            "📋 Setup:\n"
            f"• Questions: {question_count}\n"
            "• Category: Mixed\n"
            "• Difficulty: Mixed\n"
            "• Players: 2 max\n\n"
            "🍋 Rewards:\n"
            f"• Easy: +{points['easy']}\n"
            f"• Medium: +{points['medium']}\n"
            f"• Hard: +{points['hard']}\n\n"
            "🚀 Press Start when you're ready"
        )

    return (
        "🎮 Game Setup\n\n"
        "✅ Ready to Start\n\n"
        "📋 Setup:\n"
        f"• Questions: {question_count}\n"
        f"• Category: {format_category_name(category)}\n"
        "• Difficulty: Mixed\n\n"
        "🍋 Rewards:\n"
        f"• Easy: +{points['easy']}\n"
        f"• Medium: +{points['medium']}\n"
        f"• Hard: +{points['hard']}\n\n"
        "🚀 Press Start when you're ready"
    )


def render_join_text(game: dict, remaining: int) -> str:
    blink = remaining <= 10 and remaining % 2 == 0
    return build_join_text(game, remaining, blink=blink)


async def refresh_join_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    seconds_left: int | None = None,
):
    game = active_games.get(chat_id)
    if not game or game.get("status") != "joining":
        return

    join_message_id = game.get("join_message_id")
    if not join_message_id:
        return

    try:
        remaining = seconds_left
        if remaining is None:
            remaining = get_join_remaining_seconds(game)

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=join_message_id,
            text=render_join_text(game, remaining),
            reply_markup=get_join_keyboard(chat_id, game.get("mode", "solo")),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(
            "Failed to refresh join message in chat %s: %s",
            chat_id,
            e,
        )


async def cleanup_join_reminder(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = active_games.get(chat_id)
    if not game:
        return

    task = game.get("reminder_task")
    if task and not task.done():
        task.cancel()

    reminder_message_id = game.get("reminder_message_id")
    if reminder_message_id:
        await safe_delete_message(context.bot, chat_id, reminder_message_id)

    game["reminder_task"] = None
    game["reminder_message_id"] = None


async def send_join_reminders(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        game = active_games.get(chat_id)
        if not game or game.get("mode") == "duel":
            return

        join_seconds = int(game.get("join_seconds") or load_dynamic_settings()["JOIN_SECONDS"])

        if join_seconds <= 20:
            first_wait = max(1, join_seconds - 20)
        else:
            first_wait = max(1, join_seconds // 2)

        await asyncio.sleep(first_wait)

        game = active_games.get(chat_id)
        if not game or game.get("status") != "joining":
            return

        first_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="🚀 Join now before it starts!",
            reply_markup=get_join_keyboard(chat_id, game.get("mode", "solo")),
        )
        game["reminder_message_id"] = first_msg.message_id

        if join_seconds <= 20:
            return

        time_until_final = max(0, join_seconds - first_wait - 20)
        await asyncio.sleep(time_until_final)

        game = active_games.get(chat_id)
        if not game or game.get("status") != "joining":
            return

        old_reminder_id = game.get("reminder_message_id")
        if old_reminder_id:
            await safe_delete_message(context.bot, chat_id, old_reminder_id)

        final_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="⚡ Last chance to join!",
            reply_markup=get_join_keyboard(chat_id, game.get("mode", "solo")),
        )
        game["reminder_message_id"] = final_msg.message_id

    except asyncio.CancelledError:
        logger.info("Join reminders cancelled for chat %s", chat_id)
    except Exception:
        logger.exception("Reminder error in chat %s", chat_id)


async def postpone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type == "private":
        await message.reply_text("This command works only in groups.")
        return

    lock = get_game_lock(chat.id)
    async with lock:
        game = active_games.get(chat.id)

        if not game or game.get("status") != "joining":
            await message.reply_text("There is no waiting lobby to postpone.")
            return

        if game.get("mode") == "duel":
            await message.reply_text("Duel lobbies cannot be extended.")
            return

        allowed = await is_game_controller(context, chat.id, user.id, game)
        if not allowed:
            await message.reply_text("Only the game starter or an admin can postpone the lobby.")
            return

        postpone_count = int(game.get("postpone_count", 0))
        max_postpones = int(game.get("max_postpones", MAX_POSTPONES))
        postpone_seconds = int(game.get("postpone_seconds", POSTPONE_SECONDS))

        if postpone_count >= max_postpones:
            await message.reply_text("This lobby cannot be extended anymore.")
            return

        current_deadline = game.get("join_deadline")
        now = time.monotonic()

        if current_deadline is None:
            current_deadline = now

        game["join_deadline"] = max(current_deadline, now) + postpone_seconds
        game["postpone_count"] = postpone_count + 1

        remaining = get_join_remaining_seconds(game)
        extensions_left = max_postpones - game["postpone_count"]

    await refresh_join_message(context, chat.id, remaining)

    msg = await message.reply_text(
        f"⏳ Lobby extended by {postpone_seconds} seconds.\n"
        f"Time left: {remaining}s\n"
        f"Extensions left: {extensions_left}"
    )

    async def delete_later():
        await asyncio.sleep(5)
        await safe_delete_message(context.bot, chat.id, msg.message_id)

    safe_task(delete_later())


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("START GAME COMMAND RECEIVED")

    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    query = update.callback_query

    if chat:
        ensure_chat(chat)

    if not user:
        if query:
            await query.edit_message_text("❌ Could not identify user.")
        elif message:
            await message.reply_text("❌ Could not identify user.")
        return

    if not chat:
        return

    if chat.type == "private":
        if query:
            await query.edit_message_text("Use /startgame in a group.")
        elif message:
            await message.reply_text("Use /startgame in a group.")
        return

    mode = context.user_data.get("game_mode", "solo")

    lock = get_game_lock(chat.id)
    async with lock:
        if has_active_game(chat.id):
            existing_game = active_games.get(chat.id)
            text = get_existing_game_message(existing_game)

            if query:
                await query.answer(text, show_alert=True)
            elif message:
                await message.reply_text(text)
            return

        game = create_new_game_data(
            started_by=user.id,
            questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
            category=DEFAULT_CATEGORY,
            difficulty="mixed",
        )
        game["chat_id"] = chat.id
        game["setup_message_id"] = None
        game["join_message_id"] = None
        game["join_deadline"] = None
        game["join_seconds"] = None
        game["postpone_count"] = 0
        game["max_postpones"] = MAX_POSTPONES
        game["postpone_seconds"] = POSTPONE_SECONDS
        game["reminder_task"] = None
        game["reminder_message_id"] = None
        game["mode"] = mode

        if mode == "duel":
            game["category"] = "mixed"
            game["difficulty"] = "mixed"
            game["min_players"] = 2
            game["max_players"] = 2

        add_player_to_game(game, user)
        active_games[chat.id] = game

    text = format_setup_step_1_text(mode=mode)
    keyboard = get_question_count_keyboard()

    if query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=keyboard)
        setup_message_id = query.message.message_id
    else:
        msg = await message.reply_text(text, reply_markup=keyboard)
        setup_message_id = msg.message_id

    lock = get_game_lock(chat.id)
    async with lock:
        game = active_games.get(chat.id)
        if game:
            game["setup_message_id"] = setup_message_id


async def game_setup_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_dynamic_settings()
    join_seconds = settings["JOIN_SECONDS"]

    query = update.callback_query
    if not query or not query.message:
        return False

    logger.warning("SETUP CALLBACK: %s", query.data)

    data = query.data
    chat_id = query.message.chat.id

    if (
        not data.startswith("setup_")
        and data not in ("menu_back", "menu_main")
    ):
        return False

    if data in ("menu_back", "menu_main"):
        await cleanup_join_reminder(chat_id, context)
        await clear_game(context, chat_id)

        await query.edit_message_text(
            "Welcome to English Lemon !\n\n"
            "Practice vocabulary, play quiz games, and climb the leaderboard.",
            reply_markup=main_menu_keyboard(),
        )
        return True

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)

        if not game or game.get("status") not in ("setup", "joining"):
            await query.edit_message_text("No active game setup found.")
            return True

        if game["status"] == "joining" and data.startswith("setup_"):
            await query.answer("Game already started.", show_alert=True)
            return True

        mode = game.get("mode", "solo")

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

            if mode == "duel":
                game["category"] = "mixed"
                game["difficulty"] = "mixed"
                await query.edit_message_text(
                    format_setup_summary(
                        question_count=game["questions_per_game"],
                        category="mixed",
                        mode="duel",
                    ),
                    reply_markup=get_setup_confirmation_keyboard(),
                )
            else:
                await query.edit_message_text(
                    format_setup_step_2_text(count),
                    reply_markup=get_category_keyboard(),
                )

            game["setup_message_id"] = query.message.message_id
            return True

        if data == "setup_back_to_questions":
            await query.edit_message_text(
                format_setup_step_1_text(mode=mode),
                reply_markup=get_question_count_keyboard(back_callback="menu_main"),
            )
            game["setup_message_id"] = query.message.message_id
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
                    mode="solo",
                ),
                reply_markup=get_setup_confirmation_keyboard(),
            )
            game["setup_message_id"] = query.message.message_id
            return True

        if data == "setup_back_to_categories":
            await query.edit_message_text(
                format_setup_step_2_text(game["questions_per_game"]),
                reply_markup=get_category_keyboard(),
            )
            game["setup_message_id"] = query.message.message_id
            return True

        if data == "setup_start_game":
            if game.get("status") != "setup":
                await query.answer("Game already started.", show_alert=True)
                return True

            try:
                if game.get("mode") == "duel":
                    game["min_players"] = 2
                    game["max_players"] = 2
                else:
                    game["min_players"] = settings["MIN_PLAYERS"]

                game["join_seconds"] = join_seconds
                game["postpone_count"] = 0
                game["max_postpones"] = MAX_POSTPONES
                game["postpone_seconds"] = POSTPONE_SECONDS

                mark_game_joining(game, join_seconds)

                await query.edit_message_text(
                    text=render_join_text(game, join_seconds),
                    reply_markup=get_join_keyboard(chat_id, game.get("mode", "solo")),
                    parse_mode="HTML",
                )

                game["join_message_id"] = query.message.message_id
                game["setup_message_id"] = query.message.message_id

                if game.get("mode") != "duel":
                    reminder_task = safe_task(send_join_reminders(chat_id, context))
                    game["reminder_task"] = reminder_task

                safe_task(begin_game_after_join(chat_id, context))
                return True

            except Exception:
                logger.exception("Failed in setup_start_game for chat %s", chat_id)
                await query.answer("Failed to start registration.", show_alert=True)
                return True

        await query.answer()
        return True


async def begin_game_after_join(chat_id, context):
    settings = load_dynamic_settings()
    min_players = settings["MIN_PLAYERS"]

    logger.warning("BEGIN GAME AFTER JOIN: %s", chat_id)

    try:
        last_shown = None

        while True:
            lock = get_game_lock(chat_id)
            async with lock:
                game = active_games.get(chat_id)
                if not game or game["status"] != "joining":
                    return

                if game.get("mode") == "duel" and len(game["players"]) >= 2:
                    break

                actual_remaining = get_join_remaining_seconds(game)

            if actual_remaining > 10:
                shown_remaining = ((actual_remaining + 9) // 10) * 10
            else:
                shown_remaining = actual_remaining

            if shown_remaining != last_shown:
                await refresh_join_message(context, chat_id, shown_remaining)
                last_shown = shown_remaining

            if actual_remaining <= 0:
                break

            await asyncio.sleep(1)

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if not game or game["status"] != "joining":
                return

            join_message_id = game.get("join_message_id")
            reminder_message_id = game.get("reminder_message_id")

            needed_players = 2 if game.get("mode") == "duel" else min_players

            if len(game["players"]) < needed_players:
                active_games.pop(chat_id, None)
                cleanup_game_lock(chat_id)
                not_enough_players = True
                is_duel = game.get("mode") == "duel"
            else:
                game["status"] = "running"
                not_enough_players = False
                is_duel = game.get("mode") == "duel"

        if reminder_message_id:
            await safe_delete_message(context.bot, chat_id, reminder_message_id)

        await safe_delete_message(context.bot, chat_id, join_message_id)

        if not_enough_players:
            if is_duel:
                await context.bot.send_message(
                    chat_id,
                    "❌ Duel cancelled.\nNot enough players joined.",
                )
            else:
                await context.bot.send_message(
                    chat_id,
                    f"❌ Not enough players.\nGame cancelled.\n\nMinimum players needed: {min_players}",
                )
            return

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if not game or game["status"] != "running":
                return

            game["reminder_task"] = None
            game["reminder_message_id"] = None

            try:
                game["db_game_id"] = create_game(
                    chat_id=chat_id,
                    total_players=len(game["players"]),
                    total_rounds=game["questions_per_game"],
                    status="running",
                )
            except Exception:
                logger.exception("Failed to create game record for chat %s", chat_id)

        if game.get("mode") == "duel":
            await context.bot.send_message(
                chat_id,
                "⚔️ DUEL START 🍋\n\n🔥 Battle begins!\n\n⚡ First question coming..."
            )
        else:
            await context.bot.send_message(
                chat_id,
                "Game started! Get ready for the first question."
            )

        from handlers.game_play import send_question
        await send_question(chat_id, context)

    except Exception:
        logger.exception("Error in begin_game_after_join for chat %s", chat_id)