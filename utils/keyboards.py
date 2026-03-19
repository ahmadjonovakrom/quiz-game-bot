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