from telegram import InlineKeyboardButton, InlineKeyboardMarkup

LEADERBOARD_PAGE_SIZE = 15


def main_menu_keyboard(chat_type: str = "private") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Quiz", callback_data="play_quiz")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("👤 My Profile", callback_data="profile")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ])


def back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=callback_data)],
    ])


def back_cancel_keyboard(
    back_callback: str,
    cancel_callback: str = "admin_close",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=back_callback)],
        [InlineKeyboardButton("❌ Cancel", callback_data=cancel_callback)],
    ])


def leaderboard_menu_keyboard(chat_type: str) -> InlineKeyboardMarkup:
    if chat_type == "private":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🌍 All-Time", callback_data="leaderboard_global"),
                InlineKeyboardButton("📅 Daily", callback_data="leaderboard_daily"),
                InlineKeyboardButton("📊 Weekly", callback_data="leaderboard_weekly"),
            ],
            [
                InlineKeyboardButton("🗓 Monthly", callback_data="leaderboard_monthly"),
                InlineKeyboardButton("🪪 My Rank", callback_data="leaderboard_rank"),
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="menu_main"),
            ],
        ])

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 This Group", callback_data="leaderboard_group"),
            InlineKeyboardButton("🌍 All-Time", callback_data="leaderboard_global"),
        ],
        [
            InlineKeyboardButton("📅 Daily", callback_data="leaderboard_daily"),
            InlineKeyboardButton("📊 Weekly", callback_data="leaderboard_weekly"),
        ],
        [
            InlineKeyboardButton("🗓 Monthly", callback_data="leaderboard_monthly"),
            InlineKeyboardButton("🪪 My Rank", callback_data="leaderboard_rank"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="menu_main"),
        ],
    ])


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Question Management", callback_data="admin_questions")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_botstats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])


def admin_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Question", callback_data="admin_add")],
        [InlineKeyboardButton("✏️ Edit Question", callback_data="admin_edit")],
        [InlineKeyboardButton("🗑 Delete Question", callback_data="admin_delete")],
        [InlineKeyboardButton("🔎 Search Questions", callback_data="admin_search")],
        [InlineKeyboardButton("📥 Import Questions", callback_data="import_questions")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back_main")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])


def admin_confirm_keyboard(
    yes_callback: str = "admin_confirm_yes",
    no_callback: str = "admin_confirm_no",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=yes_callback),
            InlineKeyboardButton("❌ Cancel", callback_data=no_callback),
        ]
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send", callback_data="broadcast_send"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel"),
        ]
    ])


def close_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])