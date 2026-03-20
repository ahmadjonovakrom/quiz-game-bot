import logging

from telegram import Update
from telegram.ext import ContextTypes

from database import (
    get_player_profile,
    get_top_players,
    get_player_global_rank_info,
    get_daily_leaderboard_page,
    get_weekly_leaderboard_page,
    get_monthly_leaderboard_page,
    get_group_leaderboard,
    get_player_group_rank_info,
)

from utils.keyboards import leaderboard_menu_keyboard, back_keyboard

logger = logging.getLogger(__name__)


def _safe_get(row, key, default=None):
    if row is None:
        return default
    try:
        return row[key]
    except Exception:
        if isinstance(row, dict):
            return row.get(key, default)
        return default


def _extract_name(row) -> str:
    return (
        _safe_get(row, "full_name")
        or _safe_get(row, "name")
        or _safe_get(row, "username")
        or "Unknown"
    )


def _rank_prefix(index: int) -> str:
    if index == 1:
        return "🥇"
    if index == 2:
        return "🥈"
    if index == 3:
        return "🥉"
    return f"{index}."


def format_leaderboard_text(
    title: str,
    rows,
    points_key: str,
    viewer_user_id: int | None = None,
) -> str:
    if not rows:
        return (
            f"🏆 {title}\n\n"
            "No activity yet.\n"
            "Play a game to get on the leaderboard."
        )

    lines = [f"🏆 {title}", ""]

    for index, row in enumerate(rows, start=1):
        prefix = _rank_prefix(index)
        name = _extract_name(row)
        points = _safe_get(row, points_key, 0)
        is_you = viewer_user_id and _safe_get(row, "user_id") == viewer_user_id
        you_suffix = "  👈 YOU" if is_you else ""
        lines.append(f"{prefix} {name} — {points} pts{you_suffix}")

    return "\n".join(lines)


async def _send_or_edit(update: Update, text: str, reply_markup=None) -> None:
    if update.callback_query:
        query = update.callback_query
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("Failed to edit message in _send_or_edit")
            try:
                await query.message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                )
            except Exception:
                logger.exception("Failed to send fallback reply in _send_or_edit")
                raise
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
        )


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    text = "🏆 Leaderboards\n\nChoose a leaderboard:"
    await _send_or_edit(update, text, leaderboard_menu_keyboard(chat_type))


async def send_leaderboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await leaderboard(update, context)


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    profile_data, rank = get_player_profile(user.id)

    if not profile_data:
        text = (
            "👤 My Profile\n\n"
            f"Name: {user.full_name}\n"
            "Global Rank: Not ranked yet\n"
            "Points: 0\n"
            "Games Played: 0\n"
            "Correct Answers: 0"
        )
    else:
        full_name, username, total_points, games_played, correct_answers = profile_data

        lines = [
            "👤 My Profile",
            "",
            f"Name: {full_name}",
        ]
        if username:
            lines.append(f"Username: @{username}")

        lines.extend(
            [
                f"Global Rank: #{rank}" if rank else "Global Rank: Not ranked yet",
                f"Points: {total_points}",
                f"Games Played: {games_played}",
                f"Correct Answers: {correct_answers}",
            ]
        )
        text = "\n".join(lines)

    await _send_or_edit(update, text, back_keyboard("menu_main"))


async def show_global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    rows = get_top_players(limit=10)

    text = format_leaderboard_text(
        "All-Time Leaderboard",
        rows,
        points_key="total_points",
        viewer_user_id=user.id if user else None,
    )
    await _send_or_edit(update, text, back_keyboard("menu_leaderboard"))


async def show_group_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await _send_or_edit(
            update,
            "👥 This Group leaderboard is only available in groups.",
            back_keyboard("leaderboard_menu"),
        )
        return

    rows = get_group_leaderboard(chat.id, limit=10)
    text = format_leaderboard_text(
        "This Group Leaderboard",
        rows,
        points_key="total_points",
        viewer_user_id=user.id if user else None,
    )
    await _send_or_edit(update, text, back_keyboard("leaderboard_menu"))


async def show_daily_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Opening daily leaderboard for user_id=%s", user.id if user else None)

    rows = get_daily_leaderboard_page(limit=10, offset=0)

    text = format_leaderboard_text(
        "Daily Leaderboard",
        rows,
        points_key="period_points",
        viewer_user_id=user.id if user else None,
    )
    await _send_or_edit(update, text, back_keyboard("leaderboard_menu"))


async def show_weekly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Opening weekly leaderboard for user_id=%s", user.id if user else None)

    rows = get_weekly_leaderboard_page(limit=10, offset=0)

    text = format_leaderboard_text(
        "Weekly Leaderboard",
        rows,
        points_key="period_points",
        viewer_user_id=user.id if user else None,
    )
    await _send_or_edit(update, text, back_keyboard("leaderboard_menu"))


async def show_monthly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Opening monthly leaderboard for user_id=%s", user.id if user else None)

    rows = get_monthly_leaderboard_page(limit=10, offset=0)

    text = format_leaderboard_text(
        "Monthly Leaderboard",
        rows,
        points_key="period_points",
        viewer_user_id=user.id if user else None,
    )
    await _send_or_edit(update, text, back_keyboard("leaderboard_menu"))


async def show_my_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type == "private":
        rank, points = get_player_global_rank_info(user.id)
        title = "My Global Rank"

        if not rank:
            text = f"📊 {title}\n\nYou are not ranked yet."
        else:
            text = (
                f"📊 {title}\n\n"
                f"Name: {user.full_name}\n"
                f"Rank: #{rank}\n"
                f"Points: {points}"
            )

        await _send_or_edit(update, text, back_keyboard("leaderboard_menu"))
        return

    rank, points = get_player_group_rank_info(chat.id, user.id)
    title = "My Rank in This Group"

    if not rank:
        text = f"📊 {title}\n\nYou are not ranked yet."
    else:
        text = (
            f"📊 {title}\n\n"
            f"Name: {user.full_name}\n"
            f"Rank: #{rank}\n"
            f"Points: {points}"
        )

    await _send_or_edit(update, text, back_keyboard("leaderboard_menu"))


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_daily_leaderboard(update, context)


async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_weekly_leaderboard(update, context)


async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_monthly_leaderboard(update, context)


async def profile_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    logger.info("PROFILE CALLBACK DATA: %s", data)

    try:
        await query.answer()

        if data == "leaderboard_menu":
            await send_leaderboard_menu(update, context)
            return

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

        logger.warning("Unhandled profile callback data: %s", data)

    except Exception:
        logger.exception("profile_callback_handler crashed")
        raise