from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from utils.helpers import is_admin
from database import get_broadcast_chat_ids

BROADCAST_MESSAGE, BROADCAST_CONFIRM = range(100, 102)


def admin_only_text() -> str:
    return "❌ Admin only."


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Send", callback_data="broadcast_send")],
        [InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")],
    ])


async def broadcast_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END

    if not is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    context.user_data.pop("broadcast_source", None)

    await query.edit_message_text(
        "📢 Broadcast\n\n"
        "Send one of these:\n"
        "• a text message\n"
        "• a photo with caption\n"
        "• or forward/reply with a message to copy\n\n"
        "After that, I will show a preview before sending.\n\n"
        "Use /cancel to stop."
    )
    return BROADCAST_MESSAGE


async def broadcast_message_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        return ConversationHandler.END

    if not update.message:
        return BROADCAST_MESSAGE

    chat_ids = get_broadcast_chat_ids()
    if not chat_ids:
        await update.message.reply_text("No users or groups found for broadcast.")
        context.user_data.clear()
        return ConversationHandler.END

    source = update.message
    context.user_data["broadcast_source"] = {
        "chat_id": source.chat_id,
        "message_id": source.message_id,
        "recipient_count": len(chat_ids),
    }

    if source.photo:
        await update.message.reply_photo(
            photo=source.photo[-1].file_id,
            caption=(
                f"{source.caption or ''}\n\n"
                f"———\nPreview only\nRecipients: {len(chat_ids)}\n\n"
                "Send this broadcast?"
            ).strip(),
            reply_markup=broadcast_confirm_keyboard(),
        )
    elif source.text:
        await update.message.reply_text(
            f"{source.text}\n\n"
            f"———\nPreview only\nRecipients: {len(chat_ids)}\n\n"
            "Send this broadcast?",
            reply_markup=broadcast_confirm_keyboard(),
        )
    else:
        await update.message.reply_text(
            f"Preview ready.\n\nRecipients: {len(chat_ids)}\n\nSend this broadcast?",
            reply_markup=broadcast_confirm_keyboard(),
        )

    return BROADCAST_CONFIRM


async def broadcast_confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END

    if not is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return ConversationHandler.END

    await query.answer()

    if query.data == "broadcast_cancel":
        context.user_data.clear()
        await query.message.reply_text("Broadcast cancelled.")
        return ConversationHandler.END

    if query.data != "broadcast_send":
        return BROADCAST_CONFIRM

    source_data = context.user_data.get("broadcast_source")
    if not source_data:
        await query.message.reply_text("Broadcast session expired. Start again.")
        return ConversationHandler.END

    chat_ids = get_broadcast_chat_ids()
    if not chat_ids:
        context.user_data.clear()
        await query.message.reply_text("No users or groups found for broadcast.")
        return ConversationHandler.END

    sent = 0
    failed = 0

    await query.message.reply_text(f"📤 Sending broadcast to {len(chat_ids)} chat(s)...")

    for chat_id in chat_ids:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source_data["chat_id"],
                message_id=source_data["message_id"],
            )
            sent += 1
        except Exception:
            failed += 1

    await query.message.reply_text(
        "📢 Broadcast finished.\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )

    context.user_data.clear()
    return ConversationHandler.END