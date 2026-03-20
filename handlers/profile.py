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
    get_group_leaderboard_page,
    get_group_daily_leaderboard,
    get_group_weekly_leaderboard,
    get_group_monthly_leaderboard,
    get_player_group_rank_info,
    get_player_group_daily_rank_info,
    get_player_group_weekly_rank_info,
    get_player_group_monthly_rank_info,
    get_player_daily_rank_info,
    get_player_weekly_rank_info,
    get_player_monthly_rank_info,
)

from utils.keyboards import (
    leaderboard_menu_keyboard,
    leaderboard_period_keyboard,
    leaderboard_pagination_keyboard,
    back_keyboard,
)

logger = logging.getLogger(__name__)

LEADERBOARD_PAGE_SIZE = 10


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
    full_name = _safe_get(row, "full_name")
    username = _safe_get(row, "username")

    if full_name:
        return full_name
    if username:
        return f"@{username}"
    return "Unknown"


def _rank_prefix(index: int) -> str:
    if index == 1:
        return "🥇"
    if index == 2:
        return "🥈"
    if index == 3:
        return "🥉"
    return f"{index}."


def _parse_page(value: str | None) -> int:
    try:
        page = int(value or "1")
        return page if page > 0 else 1
    except Exception:
        return 1


def _offset_for_page(page: int) -> int:
    return (page - 1) * LEADERBOARD_PAGE_SIZE


def format_leaderboard_text(
    title: str,
    rows,
    points_key: str,
    viewer_user_id: int | None = None,
    viewer_rank: int | None = None,
    viewer_points: int | None = None,
    empty_message: str | None = None,
) -> str:
    if not rows:
        return (
            f"🏆 {title}\n\n"
            f"{empty_message or 'No activity yet.\nBe the first to play!'}"
        )

    lines = [f"🏆 {title}", ""]
    viewer_in_top = False

    for index, row in enumerate(rows, start=1):
        prefix = _rank_prefix(index)
        name = _extract_name(row)
        points = _safe_get(row, points_key, 0)
        is_you = bool(viewer_user_id and _safe_get(row, "user_id") == viewer_user_id)

        if is_you:
            viewer_in_top = True
            lines.append(f"{prefix} {name} — {points} 🍋 👈 YOU")
        else:
            lines.append(f"{prefix} {name} — {points} 🍋")

    if viewer_user_id and not viewer_in_top and viewer_rank:
        lines.extend([
            "",
            "──────────",
            f"👤 YOU — #{viewer_rank} — {viewer_points or 0} 🍋",
        ])

    return "\n".join(lines)


def _build_paginated_text_and_markup(
    title: str,
    rows,
    points_key: str,
    scope: str,
    period: str,
    page: int,
    viewer_user_id: int | None = None,
    viewer_rank: int | None = None,
    viewer_points: int | None = None,
    empty_message: str | None = None,
):
    visible_rows = rows[:LEADERBOARD_PAGE_SIZE]
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE

    text = format_leaderboard_text(
        title=title,
        rows=visible_rows,
        points_key=points_key,
        viewer_user_id=viewer_user_id,
        viewer_rank=viewer_rank,
        viewer_points=viewer_points,
        empty_message=empty_message,
    )

    markup = leaderboard_pagination_keyboard(
        scope=scope,
        period=period,
        page=page,
        has_next=has_next,
    )

    return text, markup


async def _send_or_edit(update: Update, text: str, reply_markup=None) -> None:
    if update.callback_query:
        query = update.callback_query
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
            )
        except Exception:
            logger.exception("Failed to edit message, sending new one instead.")
            await query.message.reply_text(
                text=text,
                reply_markup=reply_markup,
            )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=reply_markup,
        )


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    text = "🏆 Leaderboards\n\nChoose leaderboard type:"
    await _send_or_edit(update, text, leaderboard_menu_keyboard(chat_type))


async def send_leaderboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await leaderboard(update, context)


async def show_global_period_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.effective_chat.type
    text = "🌍 Global Leaderboard\n\nChoose a period:"
    await _send_or_edit(update, text, leaderboard_period_keyboard("global", chat_type))


async def show_group_period_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await _send_or_edit(
            update,
            "👥 This Group leaderboard is only available in groups.",
            back_keyboard("leaderboard_menu"),
        )
        return

    text = "👥 Group Leaderboard\n\nChoose a period:"
    await _send_or_edit(update, text, leaderboard_period_keyboard("group", chat.type))


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    profile_data, rank = get_player_profile(user.id)

    if not profile_data:
        text = (
            "👤 My Profile\n\n"
            f"Name: {user.full_name}\n"
            "Global Rank: Not ranked yet\n"
            "Lemons: 0 🍋\n"
            "Games Played: 0\n"
            "Correct Answers: 0"
        )
    else:
        full_name = _safe_get(profile_data, "full_name", user.full_name)
        username = _safe_get(profile_data, "username")
        total_points = _safe_get(profile_data, "total_points", 0)
        games_played = _safe_get(profile_data, "games_played", 0)
        correct_answers = _safe_get(profile_data, "correct_answers", 0)

        lines = [
            "👤 My Profile",
            "",
            f"Name: {full_name}",
        ]

        if username:
            lines.append(f"Username: @{username}")

        lines.extend([
            f"Global Rank: #{rank}" if rank else "Global Rank: Not ranked yet",
            f"Lemons: {total_points} 🍋",
            f"Games Played: {games_played}",
            f"Correct Answers: {correct_answers}",
        ])

        text = "\n".join(lines)

    await _send_or_edit(update, text, back_keyboard("menu_main"))


async def show_global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    try:
        user = update.effective_user
        offset = _offset_for_page(page)

        rows = get_top_players(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
        rank, points = get_player_global_rank_info(user.id) if user else (None, 0)

        text, markup = _build_paginated_text_and_markup(
            title="Global • All Time",
            rows=rows,
            points_key="total_points",
            scope="global",
            period="all",
            page=page,
            viewer_user_id=user.id if user else None,
            viewer_rank=rank,
            viewer_points=points,
            empty_message="No activity yet.\nPlay a game to become the first ranked player!",
        )

        await _send_or_edit(update, text, markup)
    except Exception:
        logger.exception("show_global_leaderboard crashed")
        await _send_or_edit(
            update,
            "❌ Global leaderboard is temporarily unavailable.",
            back_keyboard("leaderboard_scope_global"),
        )


async def show_group_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    try:
        chat = update.effective_chat
        user = update.effective_user

        if chat.type == "private":
            await _send_or_edit(
                update,
                "👥 This Group leaderboard is only available in groups.",
                back_keyboard("leaderboard_menu"),
            )
            return

        offset = _offset_for_page(page)
        rows = get_group_leaderboard_page(chat.id, limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
        rank, points = get_player_group_rank_info(chat.id, user.id)

        text, markup = _build_paginated_text_and_markup(
            title="This Group • All Time",
            rows=rows,
            points_key="total_points",
            scope="group",
            period="all",
            page=page,
            viewer_user_id=user.id if user else None,
            viewer_rank=rank,
            viewer_points=points,
            empty_message="No one has scored in this group yet.\nBe the first to play!",
        )

        await _send_or_edit(update, text, markup)
    except Exception:
        logger.exception("show_group_leaderboard crashed")
        await _send_or_edit(
            update,
            "❌ Group leaderboard is temporarily unavailable.",
            back_keyboard("leaderboard_scope_group"),
        )


async def show_daily_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    try:
        user = update.effective_user
        offset = _offset_for_page(page)

        rows = get_daily_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
        rank, points = get_player_daily_rank_info(user.id) if user else (None, 0)

        text, markup = _build_paginated_text_and_markup(
            title="Global • Daily",
            rows=rows,
            points_key="period_points",
            scope="global",
            period="daily",
            page=page,
            viewer_user_id=user.id if user else None,
            viewer_rank=rank,
            viewer_points=points,
            empty_message="No activity yet today.\nBe the first to play!",
        )

        await _send_or_edit(update, text, markup)
    except Exception:
        logger.exception("show_daily_leaderboard crashed")
        await _send_or_edit(
            update,
            "❌ Daily leaderboard is temporarily unavailable.",
            back_keyboard("leaderboard_scope_global"),
        )


async def show_weekly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    try:
        user = update.effective_user
        offset = _offset_for_page(page)

        rows = get_weekly_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
        rank, points = get_player_weekly_rank_info(user.id) if user else (None, 0)

        text, markup = _build_paginated_text_and_markup(
            title="Global • Weekly",
            rows=rows,
            points_key="period_points",
            scope="global",
            period="weekly",
            page=page,
            viewer_user_id=user.id if user else None,
            viewer_rank=rank,
            viewer_points=points,
            empty_message="No activity yet this week.\nStart the competition!",
        )

        await _send_or_edit(update, text, markup)
    except Exception:
        logger.exception("show_weekly_leaderboard crashed")
        await _send_or_edit(
            update,
            "❌ Weekly leaderboard is temporarily unavailable.",
            back_keyboard("leaderboard_scope_global"),
        )


async def show_monthly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    try:
        user = update.effective_user
        offset = _offset_for_page(page)

        rows = get_monthly_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
        rank, points = get_player_monthly_rank_info(user.id) if user else (None, 0)

        text, markup = _build_paginated_text_and_markup(
            title="Global • Monthly",
            rows=rows,
            points_key="period_points",
            scope="global",
            period="monthly",
            page=page,
            viewer_user_id=user.id if user else None,
            viewer_rank=rank,
            viewer_points=points,
            empty_message="No activity yet this month.\nBe the first to score!",
        )

        await _send_or_edit(update, text, markup)
    except Exception:
        logger.exception("show_monthly_leaderboard crashed")
        await _send_or_edit(
            update,
            "❌ Monthly leaderboard is temporarily unavailable.",
            back_keyboard("leaderboard_scope_global"),
        )


async def show_group_daily_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    try:
        chat = update.effective_chat
        user = update.effective_user

        if chat.type == "private":
            await _send_or_edit(
                update,
                "👥 This Group leaderboard is only available in groups.",
                back_keyboard("leaderboard_menu"),
            )
            return

        all_rows = get_group_daily_leaderboard(chat.id, limit=1000)
        rank, points = get_player_group_daily_rank_info(chat.id, user.id) if user else (None, 0)

        start = _offset_for_page(page)
        rows = all_rows[start:start + LEADERBOARD_PAGE_SIZE + 1]

        text, markup = _build_paginated_text_and_markup(
            title="This Group • Daily",
            rows=rows,
            points_key="period_points",
            scope="group",
            period="daily",
            page=page,
            viewer_user_id=user.id if user else None,
            viewer_rank=rank,
            viewer_points=points,
            empty_message="No activity yet today in this group.\nBe the first to play!",
        )

        await _send_or_edit(update, text, markup)
    except Exception:
        logger.exception("show_group_daily_leaderboard crashed")
        await _send_or_edit(
            update,
            "❌ Group daily leaderboard is temporarily unavailable.",
            back_keyboard("leaderboard_scope_group"),
        )


async def show_group_weekly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    try:
        chat = update.effective_chat
        user = update.effective_user

        if chat.type == "private":
            await _send_or_edit(
                update,
                "👥 This Group leaderboard is only available in groups.",
                back_keyboard("leaderboard_menu"),
            )
            return

        all_rows = get_group_weekly_leaderboard(chat.id, limit=1000)
        rank, points = get_player_group_weekly_rank_info(chat.id, user.id) if user else (None, 0)

        start = _offset_for_page(page)
        rows = all_rows[start:start + LEADERBOARD_PAGE_SIZE + 1]

        text, markup = _build_paginated_text_and_markup(
            title="This Group • Weekly",
            rows=rows,
            points_key="period_points",
            scope="group",
            period="weekly",
            page=page,
            viewer_user_id=user.id if user else None,
            viewer_rank=rank,
            viewer_points=points,
            empty_message="No activity yet this week in this group.\nStart the competition!",
        )

        await _send_or_edit(update, text, markup)
    except Exception:
        logger.exception("show_group_weekly_leaderboard crashed")
        await _send_or_edit(
            update,
            "❌ Group weekly leaderboard is temporarily unavailable.",
            back_keyboard("leaderboard_scope_group"),
        )


async def show_group_monthly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    try:
        chat = update.effective_chat
        user = update.effective_user

        if chat.type == "private":
            await _send_or_edit(
                update,
                "👥 This Group leaderboard is only available in groups.",
                back_keyboard("leaderboard_menu"),
            )
            return

        all_rows = get_group_monthly_leaderboard(chat.id, limit=1000)
        rank, points = get_player_group_monthly_rank_info(chat.id, user.id) if user else (None, 0)

        start = _offset_for_page(page)
        rows = all_rows[start:start + LEADERBOARD_PAGE_SIZE + 1]

        text, markup = _build_paginated_text_and_markup(
            title="This Group • Monthly",
            rows=rows,
            points_key="period_points",
            scope="group",
            period="monthly",
            page=page,
            viewer_user_id=user.id if user else None,
            viewer_rank=rank,
            viewer_points=points,
            empty_message="No activity yet this month in this group.\nBe the first to score!",
        )

        await _send_or_edit(update, text, markup)
    except Exception:
        logger.exception("show_group_monthly_leaderboard crashed")
        await _send_or_edit(
            update,
            "❌ Group monthly leaderboard is temporarily unavailable.",
            back_keyboard("leaderboard_scope_group"),
        )


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_daily_leaderboard(update, context)


async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_weekly_leaderboard(update, context)


async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_monthly_leaderboard(update, context)


async def global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_global_leaderboard(update, context)


async def profile_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    logger.info("PROFILE CALLBACK DATA: %s", data)
    await query.answer()

    if data == "leaderboard_menu":
        await send_leaderboard_menu(update, context)
        return

    if data == "leaderboard_scope_global":
        await show_global_period_menu(update, context)
        return

    if data == "leaderboard_scope_group":
        await show_group_period_menu(update, context)
        return

    if data == "leaderboard_global_all":
        await show_global_leaderboard(update, context, page=1)
        return

    if data == "leaderboard_global_daily":
        await show_daily_leaderboard(update, context, page=1)
        return

    if data == "leaderboard_global_weekly":
        await show_weekly_leaderboard(update, context, page=1)
        return

    if data == "leaderboard_global_monthly":
        await show_monthly_leaderboard(update, context, page=1)
        return

    if data == "leaderboard_group_all":
        await show_group_leaderboard(update, context, page=1)
        return

    if data == "leaderboard_group_daily":
        await show_group_daily_leaderboard(update, context, page=1)
        return

    if data == "leaderboard_group_weekly":
        await show_group_weekly_leaderboard(update, context, page=1)
        return

    if data == "leaderboard_group_monthly":
        await show_group_monthly_leaderboard(update, context, page=1)
        return

    if data.startswith("leaderboard_page:"):
        try:
            _, scope, period, page_str = data.split(":")
            page = _parse_page(page_str)

            if scope == "global" and period == "all":
                await show_global_leaderboard(update, context, page=page)
                return

            if scope == "global" and period == "daily":
                await show_daily_leaderboard(update, context, page=page)
                return

            if scope == "global" and period == "weekly":
                await show_weekly_leaderboard(update, context, page=page)
                return

            if scope == "global" and period == "monthly":
                await show_monthly_leaderboard(update, context, page=page)
                return

            if scope == "group" and period == "all":
                await show_group_leaderboard(update, context, page=page)
                return

            if scope == "group" and period == "daily":
                await show_group_daily_leaderboard(update, context, page=page)
                return

            if scope == "group" and period == "weekly":
                await show_group_weekly_leaderboard(update, context, page=page)
                return

            if scope == "group" and period == "monthly":
                await show_group_monthly_leaderboard(update, context, page=page)
                return

        except Exception:
            logger.exception("Failed to handle leaderboard pagination callback")
            await _send_or_edit(
                update,
                "❌ Could not open that leaderboard page.",
                back_keyboard("leaderboard_menu"),
            )
            return

    if data == "profile":
        await profile(update, context)
        return

    logger.warning("Unhandled profile callback data: %s", data)