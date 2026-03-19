from telegram import Update
from telegram.ext import ContextTypes

from database import (
    ensure_player,
    get_player,
    get_player_rank,
    get_global_leaderboard_page,
    get_group_leaderboard_page,
    get_player_global_rank_info,
    get_player_group_rank_info,
    get_daily_leaderboard_page,
    get_weekly_leaderboard_page,
    get_monthly_leaderboard_page,
    get_player_daily_rank_info,
    get_player_weekly_rank_info,
    get_player_monthly_rank_info,
)
from utils.keyboards import (
    back_keyboard,
    leaderboard_menu_keyboard,
    leaderboard_pagination_keyboard,
)
from utils.texts import (
    format_leaderboard_menu_text,
    format_leaderboard_text,
    format_my_rank_text,
    format_profile_text,
)

LEADERBOARD_PAGE_SIZE = 15


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    ensure_player(user)

    player = get_player(user.id)
    global_rank = get_player_rank(user.id)

    group_rank = None
    group_points = None
    if chat.type in ("group", "supergroup"):
        group_rank, group_points = get_player_group_rank_info(chat.id, user.id)

    text = format_profile_text(
        player=player,
        global_rank=global_rank,
        chat_type=chat.type,
        group_rank=group_rank,
        group_points=group_points,
    )

    reply_markup = back_keyboard("menu_main")

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(text, reply_markup=reply_markup)


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = update.effective_chat
    user = update.effective_user
    ensure_player(user)

    if query:
        if chat.type == "private":
            await show_global_leaderboard(query, user.id, 0)
        else:
            await show_group_leaderboard(query, user.id, chat.id, 0)
    else:
        if chat.type == "private":
            await send_global_leaderboard_message(update.effective_message, user.id, 0)
        else:
            await send_group_leaderboard_message(update.effective_message, chat.id, user.id, 0)


async def global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    ensure_player(user)

    if query:
        await show_global_leaderboard(query, user.id, 0)
    else:
        await send_global_leaderboard_message(update.effective_message, user.id, 0)


async def daily_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    ensure_player(user)

    if query:
        await show_daily_leaderboard(query, user.id, 0)
    else:
        await send_daily_leaderboard_message(update.effective_message, user.id, 0)


async def weekly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    ensure_player(user)

    if query:
        await show_weekly_leaderboard(query, user.id, 0)
    else:
        await send_weekly_leaderboard_message(update.effective_message, user.id, 0)


async def monthly_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    ensure_player(user)

    if query:
        await show_monthly_leaderboard(query, user.id, 0)
    else:
        await send_monthly_leaderboard_message(update.effective_message, user.id, 0)


async def send_leaderboard_menu(query):
    chat_type = query.message.chat.type
    await query.edit_message_text(
        format_leaderboard_menu_text(),
        reply_markup=leaderboard_menu_keyboard(chat_type),
    )


async def send_global_leaderboard_message(message, user_id: int, offset: int):
    rows = get_global_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_global_rank_info(user_id)

    text = format_leaderboard_text(
        "🌍 Global Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await message.reply_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("global", offset, has_next),
    )


async def send_group_leaderboard_message(message, chat_id: int, user_id: int, offset: int):
    rows = get_group_leaderboard_page(
        chat_id=chat_id,
        limit=LEADERBOARD_PAGE_SIZE + 1,
        offset=offset,
    )
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_group_rank_info(chat_id, user_id)

    text = format_leaderboard_text(
        "👥 Group Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await message.reply_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("group", offset, has_next),
    )


async def send_daily_leaderboard_message(message, user_id: int, offset: int):
    rows = get_daily_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_daily_rank_info(user_id)

    text = format_leaderboard_text(
        "📅 Daily Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await message.reply_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("daily", offset, has_next),
    )


async def send_weekly_leaderboard_message(message, user_id: int, offset: int):
    rows = get_weekly_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_weekly_rank_info(user_id)

    text = format_leaderboard_text(
        "📊 Weekly Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await message.reply_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("weekly", offset, has_next),
    )


async def send_monthly_leaderboard_message(message, user_id: int, offset: int):
    rows = get_monthly_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_monthly_rank_info(user_id)

    text = format_leaderboard_text(
        "🗓 Monthly Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await message.reply_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("monthly", offset, has_next),
    )


async def show_global_leaderboard(query, user_id: int, offset: int):
    rows = get_global_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_global_rank_info(user_id)

    text = format_leaderboard_text(
        "🌍 Global Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await query.edit_message_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("global", offset, has_next),
    )


async def show_group_leaderboard(query, user_id: int, chat_id: int, offset: int):
    rows = get_group_leaderboard_page(
        chat_id=chat_id,
        limit=LEADERBOARD_PAGE_SIZE + 1,
        offset=offset,
    )
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_group_rank_info(chat_id, user_id)

    text = format_leaderboard_text(
        "👥 Group Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await query.edit_message_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("group", offset, has_next),
    )


async def show_daily_leaderboard(query, user_id: int, offset: int):
    rows = get_daily_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_daily_rank_info(user_id)

    text = format_leaderboard_text(
        "📅 Daily Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await query.edit_message_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("daily", offset, has_next),
    )


async def show_weekly_leaderboard(query, user_id: int, offset: int):
    rows = get_weekly_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_weekly_rank_info(user_id)

    text = format_leaderboard_text(
        "📊 Weekly Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await query.edit_message_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("weekly", offset, has_next),
    )


async def show_monthly_leaderboard(query, user_id: int, offset: int):
    rows = get_monthly_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_monthly_rank_info(user_id)

    text = format_leaderboard_text(
        "🗓 Monthly Leaderboard",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await query.edit_message_text(
        text,
        reply_markup=leaderboard_pagination_keyboard("monthly", offset, has_next),
    )


async def show_my_rank(query, user_id: int, chat_type: str, chat_id: int):
    global_rank, global_points = get_player_global_rank_info(user_id)

    group_rank = None
    group_points = None
    if chat_type != "private":
        group_rank, group_points = get_player_group_rank_info(chat_id, user_id)

    text = format_my_rank_text(
        global_rank=global_rank,
        global_points=global_points,
        chat_type=chat_type,
        group_rank=group_rank,
        group_points=group_points,
    )

    await query.edit_message_text(
        text,
        reply_markup=leaderboard_menu_keyboard(chat_type),
    )


async def profile_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat.id
    chat_type = query.message.chat.type

    if data == "lb_myrank":
        await show_my_rank(query, user_id, chat_type, chat_id)
        return

    if data.startswith("lb_global_"):
        offset = int(data.split("_")[-1])
        await show_global_leaderboard(query, user_id, offset)
        return

    if data.startswith("lb_group_"):
        offset = int(data.split("_")[-1])
        await show_group_leaderboard(query, user_id, chat_id, offset)
        return

    if data.startswith("lb_daily_"):
        offset = int(data.split("_")[-1])
        await show_daily_leaderboard(query, user_id, offset)
        return

    if data.startswith("lb_weekly_"):
        offset = int(data.split("_")[-1])
        await show_weekly_leaderboard(query, user_id, offset)
        return

    if data.startswith("lb_monthly_"):
        offset = int(data.split("_")[-1])
        await show_monthly_leaderboard(query, user_id, offset)
        return