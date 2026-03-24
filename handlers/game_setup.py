import asyncio
import logging

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
    is_running_game_controller,
)
from utils.keyboards import (
    game_setup_questions_keyboard,
    game_setup_categories_keyboard,
    game_setup_confirm_keyboard,
    main_menu_keyboard,
)
from services.game_service import (
    active_games,
    poll_map,
    get_game_lock,
    cleanup_game_lock,
    clear_game,
    create_new_game_data,
    get_existing_game_message,
    add_player_to_game,
    mark_game_joining,
)

from handlers.game_results import show_saved_results

logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "mixed": "Mixed",
    "vocabulary": "Vocabulary",
    "grammar": "Grammar",
    "idioms_phrases": "Idioms & Phrases",
    "synonyms": "Synonyms",
    "collocations": "Collocations",
}


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
    return CATEGORY_LABELS.get(str(category).lower(), str(category).replace("_", " ").title())


def get_question_count_keyboard(back_callback: str = "menu_main"):
    return game_setup_questions_keyboard(back_callback)


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
    settings = load_dynamic_settings()
    points = settings["POINTS"]

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


async def refresh_join_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    settings = load_dynamic_settings()
    join_seconds = settings["JOIN_SECONDS"]

    game = active_games.get(chat_id)
    if not game or game.get("status") != "joining":
        return

    join_message_id = game.get("join_message_id")
    if not join_message_id:
        return

    display_remaining = game.get("display_remaining", join_seconds)
    blink = game.get("display_blink", False)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=join_message_id,
            text=build_join_text(game, display_remaining, blink=blink),
            reply_markup=get_join_keyboard(chat_id),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Failed to refresh join message in chat %s: %s", chat_id, e)


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
        else:
            await message.reply_text("❌ Could not identify user.")
        return

    if chat.type == "private":
        if query:
            await query.edit_message_text("Use /startgame in a group.")
        else:
            await message.reply_text("Use /startgame in a group.")
        return

    lock = get_game_lock(chat.id)
    async with lock:
        if has_active_game(chat.id):
            existing_game = active_games.get(chat.id)
            text = get_existing_game_message(existing_game)

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


async def game_setup_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_dynamic_settings()
    join_seconds = settings["JOIN_SECONDS"]

    query = update.callback_query
    logger.warning("SETUP CALLBACK: %s", query.data)

    data = query.data

    if (
        not data.startswith("setup_")
        and data not in ("menu_back", "menu_main")
        and not data.startswith("setup_back_to_results:")
    ):
        return False

    user = query.from_user
    chat_id = query.message.chat.id

    if data.startswith("setup_back_to_results:"):
        try:
            _, _, game_id_str = data.split(":")
            game_id = int(game_id_str)
        except Exception:
            await query.answer("Error.", show_alert=True)
            return True

        game = active_games.get(chat_id)
        if game:
            current_poll_id = game.get("current_poll_id")
            if current_poll_id:
                poll_map.pop(current_poll_id, None)

            active_games.pop(chat_id, None)
            cleanup_game_lock(chat_id)

        await show_saved_results(query, context, game_id)
        return True

    if data in ("menu_back", "menu_main"):
        game = active_games.get(chat_id)

        if game and game.get("return_to_results"):
            game_id = game["return_to_results"]

            current_poll_id = game.get("current_poll_id")
            if current_poll_id:
                poll_map.pop(current_poll_id, None)

            active_games.pop(chat_id, None)
            cleanup_game_lock(chat_id)

            await show_saved_results(query, context, game_id)
            return True

        if game:
            status = game.get("status")

            if status == "running":
                allowed = await is_running_game_controller(context, chat_id, user.id)
                if not allowed:
                    await query.answer(
                        "Only a group admin can control a running game.",
                        show_alert=True,
                    )
                    return True
            else:
                allowed = await is_game_controller(context, chat_id, user.id, game)
                if not allowed:
                    await query.answer(
                        "Only the game starter or a group admin can do this.",
                        show_alert=True,
                    )
                    return True

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

        restricted_actions = set()  # no restrictions in setup

        if data in restricted_actions:
            status = game.get("status")

            if status == "running":
                allowed = await is_game_controller(context, chat_id, user.id, game)
                if not allowed:
                    await query.answer(
                        "Only a group admin can control a running game.",
                        show_alert=True,
                    )
                    return True
            else:
                allowed = await is_game_controller(context, chat_id, user.id, game)
                if not allowed:
                    await query.answer(
                        "Only the game starter or a group admin can do this.",
                        show_alert=True,
                    )
                    return True

        if game["status"] == "joining" and data.startswith("setup_"):
            await query.answer("Game already started.", show_alert=True)
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
            back_callback = "menu_main"
            if game.get("return_to_results"):
                back_callback = f"setup_back_to_results:{game['return_to_results']}"

            await query.edit_message_text(
                format_setup_step_1_text(),
                reply_markup=get_question_count_keyboard(back_callback=back_callback),
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
            if game.get("status") != "setup":
                await query.answer("Game already started.", show_alert=True)
                return True

            try:
                game["min_players"] = settings["MIN_PLAYERS"]
                mark_game_joining(game, join_seconds)

                await query.edit_message_text(
                    text=build_join_text(game, join_seconds),
                    reply_markup=get_join_keyboard(chat_id),
                    parse_mode="HTML",
                )

                game["join_message_id"] = query.message.message_id

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
    join_seconds = settings["JOIN_SECONDS"]

    logger.warning("BEGIN GAME AFTER JOIN: %s", chat_id)

    try:
        loop = asyncio.get_event_loop()

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if not game or game["status"] != "joining":
                return

            game["join_end_time"] = loop.time() + join_seconds
            game["display_remaining"] = join_seconds
            game["display_blink"] = False

        last_display_value = None
        last_blink = None

        while True:
            lock = get_game_lock(chat_id)
            async with lock:
                game = active_games.get(chat_id)
                if not game or game["status"] != "joining":
                    return

                end_time = game.get("join_end_time")
                if end_time is None:
                    return

                actual_remaining = max(0, int(end_time - loop.time()))

                if actual_remaining > 10:
                    display_value = ((actual_remaining + 9) // 10) * 10
                    display_value = min(display_value, join_seconds)
                    blink = False
                else:
                    display_value = actual_remaining
                    blink = (actual_remaining % 2 == 0)

                game["display_remaining"] = display_value
                game["display_blink"] = blink

            if display_value != last_display_value or blink != last_blink:
                await refresh_join_message(context, chat_id)
                last_display_value = display_value
                last_blink = blink

            if actual_remaining <= 0:
                break

            await asyncio.sleep(1)

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if not game or game["status"] != "joining":
                return

            join_message_id = game.get("join_message_id")

            if len(game["players"]) < min_players:
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
                f"❌ Not enough players.\nGame cancelled.\n\nMinimum players needed: {min_players}",
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

        await context.bot.send_message(
            chat_id,
            "Game started! Get ready for the first question."
        )

        from handlers.game import send_question
        await send_question(chat_id, context)

    except Exception:
        logger.exception("Error in begin_game_after_join for chat %s", chat_id)