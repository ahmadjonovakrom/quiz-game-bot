import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import DEFAULT_QUESTIONS_PER_GAME
from services.game_service import (
    active_games,
    get_game_lock,
    create_new_game_data,
    get_existing_game_message,
    add_player_to_game,
)
from handlers.game_setup import has_active_game, get_question_count_keyboard

logger = logging.getLogger(__name__)

# kept only so existing imports won't break
active_duels = {}


async def handle_duel_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Duel now uses the normal shared game flow.
    return


async def challenge_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()

    chat = query.message.chat
    user = query.from_user

    if chat.type == "private":
        await query.edit_message_text(
            "⚔️ Challenge works only in groups.\n\n"
            "Add English Lemon to a group and start a 1 vs 1 duel there."
        )
        return

    chat_id = chat.id

    lock = get_game_lock(chat_id)
    async with lock:
        if has_active_game(chat_id):
            existing_game = active_games.get(chat_id)
            await query.answer(
                get_existing_game_message(existing_game),
                show_alert=True,
            )
            return

        game = create_new_game_data(
            started_by=user.id,
            questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
            category="mixed",
            difficulty="mixed",
        )
        game["chat_id"] = chat_id
        game["mode"] = "duel"
        game["category"] = "mixed"
        game["difficulty"] = "mixed"
        game["min_players"] = 2
        game["max_players"] = 2
        game["setup_message_id"] = query.message.message_id
        game["join_message_id"] = None
        game["join_deadline"] = None
        game["join_seconds"] = None
        game["reminder_task"] = None
        game["reminder_message_id"] = None

        add_player_to_game(game, user)
        active_games[chat_id] = game

    await query.edit_message_text(
        "⚔️ Duel Setup\n\n"
        "Step 1 of 1 — Choose number of questions\n\n"
        "• Mode: 1 vs 1\n"
        "• Category: Mixed\n"
        "• Difficulty: Mixed",
        reply_markup=get_question_count_keyboard(back_callback="menu_main"),
    )