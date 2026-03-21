from telegram import Update
from telegram.ext import ContextTypes

from handlers.profile import (
    show_group_leaderboard,
    show_group_daily_leaderboard,
    show_group_weekly_leaderboard,
    show_group_monthly_leaderboard,
)


async def group_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_group_leaderboard(update, context, page=1)


async def group_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_group_daily_leaderboard(update, context, page=1)


async def group_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_group_weekly_leaderboard(update, context, page=1)


async def group_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_group_monthly_leaderboard(update, context, page=1)


async def group_leaderboard_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "group_lb_all":
        await show_group_leaderboard(update, context, page=1)
        return

    if data == "group_lb_daily":
        await show_group_daily_leaderboard(update, context, page=1)
        return

    if data == "group_lb_weekly":
        await show_group_weekly_leaderboard(update, context, page=1)
        return

    if data == "group_lb_monthly":
        await show_group_monthly_leaderboard(update, context, page=1)
        return