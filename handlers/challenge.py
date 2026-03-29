import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.game_service import active_games, get_game_lock, get_existing_game_message
from handlers.game_setup import (
    has_active_game,
    format_setup_step_1_text,
    get_question_count_keyboard,
)

logger = logging.getLogger(__name__)

# kept only so existing imports won't break
active_duels = {}


async def handle_duel_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Duel is handled through the normal game flow now.
    return


async def challenge_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.message:
        return

    chat = query.message.chat
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

    context.user_data["game_mode"] = "duel"

    await query.edit_message_text(
        "⚔️ Duel Setup\n\n"
        "Step 1 of 1 — Choose number of questions\n\n"
        "• Mode: 1 vs 1\n"
        "• Difficulty: Mixed\n"
        "• Category: Mixed",
        reply_markup=get_question_count_keyboard(back_callback="menu_main"),
    )