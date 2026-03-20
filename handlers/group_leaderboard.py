from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_group_leaderboard,
    get_group_daily_leaderboard,
    get_group_weekly_leaderboard,
    get_group_monthly_leaderboard,
)


def group_leaderboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏆 All-Time", callback_data="group_lb_all"),
            InlineKeyboardButton("📅 Daily", callback_data="group_lb_daily"),
        ],
        [
            InlineKeyboardButton("📈 Weekly", callback_data="group_lb_weekly"),
            InlineKeyboardButton("🗓 Monthly", callback_data="group_lb_monthly"),
        ],
    ])


def _format_group_leaderboard_text(rows, title: str, group_name: str) -> str:
    text = f"🏆 {title}\n"
    text += f"📍 Group: {group_name}\n\n"

    if not rows:
        text += "No data yet."
        return text

    medals = ["🥇", "🥈", "🥉"]

    for i, row in enumerate(rows, start=1):
        icon = medals[i - 1] if i <= 3 else f"{i}."
        name = row["full_name"] or row["username"] or f"User {row['user_id']}"
        points = row["period_points"] if "period_points" in row.keys() else row["total_points"]
        text += f"{icon} {name} — {points} pts\n"

    return text


def _get_group_rows(chat_id: int, period: str, limit: int = 10):
    if period == "daily":
        return get_group_daily_leaderboard(chat_id, limit=limit)
    if period == "weekly":
        return get_group_weekly_leaderboard(chat_id, limit=limit)
    if period == "monthly":
        return get_group_monthly_leaderboard(chat_id, limit=limit)
    return get_group_leaderboard(chat_id, limit=limit)


def _get_group_title(period: str) -> str:
    titles = {
        "all": "Group Leaderboard • All-Time",
        "daily": "Group Leaderboard • Daily",
        "weekly": "Group Leaderboard • Weekly",
        "monthly": "Group Leaderboard • Monthly",
    }
    return titles.get(period, "Group Leaderboard • All-Time")


async def _send_group_leaderboard(update: Update, period: str):
    chat = update.effective_chat

    if chat.type == "private":
        await update.effective_message.reply_text("This command only works in groups.")
        return

    rows = _get_group_rows(chat.id, period, limit=10)
    text = _format_group_leaderboard_text(
        rows,
        _get_group_title(period),
        chat.title or "This Group",
    )

    await update.effective_message.reply_text(
        text,
        reply_markup=group_leaderboard_keyboard(),
    )


async def group_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_leaderboard(update, "all")


async def group_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_leaderboard(update, "daily")


async def group_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_leaderboard(update, "weekly")


async def group_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_group_leaderboard(update, "monthly")


async def group_leaderboard_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat

    if chat.type == "private":
        await query.edit_message_text("This menu only works in groups.")
        return

    period_map = {
        "group_lb_all": "all",
        "group_lb_daily": "daily",
        "group_lb_weekly": "weekly",
        "group_lb_monthly": "monthly",
    }

    period = period_map.get(query.data)
    if not period:
        return

    rows = _get_group_rows(chat.id, period, limit=10)
    text = _format_group_leaderboard_text(
        rows,
        _get_group_title(period),
        chat.title or "This Group",
    )

    await query.edit_message_text(
        text,
        reply_markup=group_leaderboard_keyboard(),
    )