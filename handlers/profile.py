# handlers/profile.py

from telegram import Update
from telegram.ext import ContextTypes

from utils.keyboards import (
    leaderboard_menu_keyboard,
    back_keyboard,
)
from services.profile_service import (
    get_profile_text_for_user,
    get_global_leaderboard_text,
    get_group_leaderboard_text,
    get_daily_leaderboard_text,
    get_weekly_leaderboard_text,
    get_monthly_leaderboard_text,
    get_global_rank_text,
    get_group_rank_text,
)


async def _send_or_edit(update: Update, text: str, reply_markup=None) -> None:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
        except Exception:
            await query.message.reply_text(text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    text = "🏆 Leaderboards\n\nChoose a leaderboard:"
    await _send_or_edit(
        update,
        text,
        leaderboard_menu_keyboard(chat_type),
    )


async def send_leaderboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await leaderboard(update, context)


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = get_profile_text_for_user(user.id, user)
    await _send_or_edit(update, text, back_keyboard("menu_main"))


async def show_global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_global_leaderboard_text(limit=10, offset=0)
    await _send_or_edit(update, text, back_keyboard("menu_leaderboard"))


async def show_group_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await _send_or_edit(
            update,
            "👥 This Group leaderboard is only available in groups.",
            back_keyboard("menu_leaderboard"),
        )
        return

    text = get_group_leaderboard_text(chat.id, limit=10, offset=0)
    await _send_or_edit(update, text, back_keyboard("menu_leaderboard"))


async def show_daily_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_daily_leaderboard_text(limit=10, offset=0)
    await _send_or_edit(update, text, back_keyboard("menu_leaderboard"))


async def show_weekly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_weekly_leaderboard_text(limit=10, offset=0)
    await _send_or_edit(update, text, back_keyboard("menu_leaderboard"))


async def show_monthly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_monthly_leaderboard_text(limit=10, offset=0)
    await _send_or_edit(update, text, back_keyboard("menu_leaderboard"))


async def show_my_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type == "private":
        text = get_global_rank_text(user.id, user.full_name)
        await _send_or_edit(update, text, back_keyboard("menu_leaderboard"))
        return

    text = get_group_rank_text(chat.id, user.id, user.full_name)
    await _send_or_edit(update, text, back_keyboard("menu_leaderboard"))


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_daily_leaderboard(update, context)


async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_weekly_leaderboard(update, context)


async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_monthly_leaderboard(update, context)


async def profile_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "leaderboard_global":
        await show_global_leaderboard(update, context)
        return

    if data == "leaderboard_group":
        await show_group_leaderboard(update, context)
        return

    if data == "leaderboard_daily":
        await show_daily_leaderboard(update, context)
        return

    if data == "leaderboard_weekly":
        await show_weekly_leaderboard(update, context)
        return

    if data == "leaderboard_monthly":
        await show_monthly_leaderboard(update, context)
        return

    if data == "leaderboard_rank":
        await show_my_rank(update, context)
        return

    if data == "profile":
        await profile(update, context)
        return