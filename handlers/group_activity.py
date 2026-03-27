from telegram import Update
from telegram.ext import ContextTypes

from database import ensure_chat, ensure_group_player


async def track_group_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if chat.type not in ("group", "supergroup"):
        return

    if user.is_bot:
        return

    ensure_chat(chat)
    ensure_group_player(chat.id, user)