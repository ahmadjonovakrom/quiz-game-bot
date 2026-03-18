from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    ensure_player,
    get_player,
    get_player_rank,
    get_global_leaderboard_page,
    get_group_leaderboard_page,
    get_player_global_rank_info,
    get_player_group_rank_info,
)

LEADERBOARD_PAGE_SIZE = 15


def medal(rank_number: int) -> str:
    if rank_number == 1:
        return "🥇"
    if rank_number == 2:
        return "🥈"
    if rank_number == 3:
        return "🥉"
    return f"{rank_number}."


def display_name_from_row(row) -> str:
    if row["username"]:
        return f"@{row['username']}"
    return row["full_name"] or f"User {row['user_id']}"


def build_leaderboard_menu(chat_type: str) -> InlineKeyboardMarkup:
    if chat_type == "private":
        keyboard = [
            [InlineKeyboardButton("🌍 Global", callback_data="lb_global_0")],
            [InlineKeyboardButton("👤 My Rank", callback_data="lb_myrank")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("👥 This Group", callback_data="lb_group_0")],
            [InlineKeyboardButton("🌍 Global", callback_data="lb_global_0")],
            [InlineKeyboardButton("👤 My Rank", callback_data="lb_myrank")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
        ]

    return InlineKeyboardMarkup(keyboard)


def build_pagination_keyboard(kind: str, offset: int, has_next: bool) -> InlineKeyboardMarkup:
    rows = []

    nav = []
    if offset > 0:
        prev_offset = max(0, offset - LEADERBOARD_PAGE_SIZE)
        nav.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=f"lb_{kind}_{prev_offset}"
            )
        )

    if has_next:
        next_offset = offset + LEADERBOARD_PAGE_SIZE
        nav.append(
            InlineKeyboardButton(
                "➡️ Next",
                callback_data=f"lb_{kind}_{next_offset}"
            )
        )

    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🔙 Back", callback_data="menu_leaderboard")])
    return InlineKeyboardMarkup(rows)


def build_leaderboard_text(title: str, rows, offset: int, my_rank, my_points) -> str:
    lines = [title, ""]

    for i, row in enumerate(rows, start=offset + 1):
        name = display_name_from_row(row)
        lines.append(f"{medal(i)} {name} — {row['total_points']} 🍋")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━")
    lines.append(f"👤 Your rank: #{my_rank if my_rank else '-'}")
    lines.append(f"🍋 Your points: {my_points}")

    return "\n".join(lines)


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    ensure_player(user)

    player = get_player(user.id)
    global_rank = get_player_rank(user.id)

    if not player:
        await message.reply_text("No profile data yet.")
        return

    display_name = f"@{player['username']}" if player["username"] else player["full_name"]
    fastest = player["fastest_answer_time"]
    fastest_text = f"{fastest:.2f}s" if fastest is not None else "—"

    text_lines = [
        "👤 Player Profile",
        "",
        f"Name: {display_name}",
        f"Games played: {player['games_played']}",
        f"Games won: {player['games_won']}",
        f"Correct answers: {player['correct_answers']}",
        f"Wrong answers: {player['wrong_answers']}",
        f"Best streak: {player['best_streak']}",
        f"Total points: {player['total_points']}",
        f"Fastest answer: {fastest_text}",
        f"Global rank: #{global_rank if global_rank else '-'}",
    ]

    if chat.type in ("group", "supergroup"):
        group_rank, group_points = get_player_group_rank_info(chat.id, user.id)
        text_lines.append(f"Group rank: #{group_rank if group_rank else '-'}")
        text_lines.append(f"Group points: {group_points}")

    await message.reply_text("\n".join(text_lines))


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    ensure_player(user)

    if chat.type == "private":
        await send_global_leaderboard_message(update.effective_message, user.id, 0)
    else:
        await send_group_leaderboard_message(update.effective_message, chat.id, user.id, 0)


async def global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    await send_global_leaderboard_message(update.effective_message, user.id, 0)


async def send_leaderboard_menu(query):
    chat_type = query.message.chat.type
    await query.edit_message_text(
        "🏆 Leaderboard\n\nChoose one:",
        reply_markup=build_leaderboard_menu(chat_type),
    )


async def send_global_leaderboard_message(message, user_id: int, offset: int):
    rows = get_global_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_global_rank_info(user_id)

    text = build_leaderboard_text(
        "🌍 GLOBAL LEADERBOARD",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await message.reply_text(
        text,
        reply_markup=build_pagination_keyboard("global", offset, has_next),
    )


async def send_group_leaderboard_message(message, chat_id: int, user_id: int, offset: int):
    rows = get_group_leaderboard_page(
        chat_id=chat_id,
        limit=LEADERBOARD_PAGE_SIZE + 1,
        offset=offset
    )
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_group_rank_info(chat_id, user_id)

    text = build_leaderboard_text(
        "🏆 GROUP LEADERBOARD",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await message.reply_text(
        text,
        reply_markup=build_pagination_keyboard("group", offset, has_next),
    )


async def show_global_leaderboard(query, user_id: int, offset: int):
    rows = get_global_leaderboard_page(limit=LEADERBOARD_PAGE_SIZE + 1, offset=offset)
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_global_rank_info(user_id)

    text = build_leaderboard_text(
        "🌍 GLOBAL LEADERBOARD",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await query.edit_message_text(
        text,
        reply_markup=build_pagination_keyboard("global", offset, has_next),
    )


async def show_group_leaderboard(query, user_id: int, chat_id: int, offset: int):
    rows = get_group_leaderboard_page(
        chat_id=chat_id,
        limit=LEADERBOARD_PAGE_SIZE + 1,
        offset=offset
    )
    has_next = len(rows) > LEADERBOARD_PAGE_SIZE
    rows = rows[:LEADERBOARD_PAGE_SIZE]

    my_rank, my_points = get_player_group_rank_info(chat_id, user_id)

    text = build_leaderboard_text(
        "🏆 GROUP LEADERBOARD",
        rows,
        offset,
        my_rank,
        my_points,
    )

    await query.edit_message_text(
        text,
        reply_markup=build_pagination_keyboard("group", offset, has_next),
    )


async def show_my_rank(query, user_id: int, chat_type: str, chat_id: int):
    global_rank, global_points = get_player_global_rank_info(user_id)

    lines = [
        "👤 MY RANK",
        "",
        f"🌍 Global rank: #{global_rank if global_rank else '-'}",
        f"🍋 Global points: {global_points}",
    ]

    if chat_type != "private":
        group_rank, group_points = get_player_group_rank_info(chat_id, user_id)
        lines.append("")
        lines.append(f"👥 Group rank: #{group_rank if group_rank else '-'}")
        lines.append(f"🍋 Group points: {group_points}")

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=build_leaderboard_menu(chat_type),
    )


async def profile_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat.id
    chat_type = query.message.chat.type

    if data == "menu_leaderboard":
        await send_leaderboard_menu(query)
        return

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