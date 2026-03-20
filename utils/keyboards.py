from telegram import InlineKeyboardButton, InlineKeyboardMarkup


LEADERBOARD_PAGE_SIZE = 15


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Quiz", callback_data="menu_play")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("👤 My Profile", callback_data="menu_profile")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ])


def back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=callback_data)],
    ])


def leaderboard_menu_keyboard(chat_type: str) -> InlineKeyboardMarkup:
    if chat_type == "private":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🌍 Global", callback_data="leaderboard_scope_global")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")],
        ])

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌍 Global", callback_data="leaderboard_scope_global"),
            InlineKeyboardButton("👥 Group", callback_data="leaderboard_scope_group"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")],
    ])


def leaderboard_period_keyboard(scope: str, chat_type: str) -> InlineKeyboardMarkup:
    rows = []

    if scope == "global":
        rows.extend([
            [InlineKeyboardButton("🏆 All Time", callback_data="leaderboard_global_all")],
            [
                InlineKeyboardButton("📅 Daily", callback_data="leaderboard_global_daily"),
                InlineKeyboardButton("🗓 Weekly", callback_data="leaderboard_global_weekly"),
            ],
            [InlineKeyboardButton("📆 Monthly", callback_data="leaderboard_global_monthly")],
        ])
    elif scope == "group":
        if chat_type == "private":
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="leaderboard_menu")],
            ])

        rows.extend([
            [InlineKeyboardButton("🏆 All Time", callback_data="leaderboard_group_all")],
            [
                InlineKeyboardButton("📅 Daily", callback_data="leaderboard_group_daily"),
                InlineKeyboardButton("🗓 Weekly", callback_data="leaderboard_group_weekly"),
            ],
            [InlineKeyboardButton("📆 Monthly", callback_data="leaderboard_group_monthly")],
        ])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="leaderboard_menu")])
    return InlineKeyboardMarkup(rows)


def leaderboard_pagination_keyboard(
    scope: str,
    period: str,
    page: int,
    has_next: bool,
) -> InlineKeyboardMarkup:
    nav_row = []

    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                "⬅️ Prev",
                callback_data=f"leaderboard_page:{scope}:{period}:{page - 1}",
            )
        )

    if has_next:
        nav_row.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=f"leaderboard_page:{scope}:{period}:{page + 1}",
            )
        )

    rows = []
    if nav_row:
        rows.append(nav_row)

    if scope == "global":
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data="leaderboard_scope_global")])
    else:
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data="leaderboard_scope_group")])

    return InlineKeyboardMarkup(rows)


def game_setup_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5", callback_data="setup_questions_5"),
            InlineKeyboardButton("10", callback_data="setup_questions_10"),
        ],
        [
            InlineKeyboardButton("15", callback_data="setup_questions_15"),
            InlineKeyboardButton("20", callback_data="setup_questions_20"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="menu_main"),
        ],
    ])


def game_setup_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Mixed", callback_data="setup_category_mixed"),
            InlineKeyboardButton("Vocabulary", callback_data="setup_category_vocabulary"),
        ],
        [
            InlineKeyboardButton("Grammar", callback_data="setup_category_grammar"),
            InlineKeyboardButton("Idioms & Phrases", callback_data="setup_category_idioms_phrases"),
        ],
        [
            InlineKeyboardButton("Synonyms", callback_data="setup_category_synonyms"),
            InlineKeyboardButton("Collocations", callback_data="setup_category_collocations"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="setup_back_to_questions"),
        ],
    ])


def game_setup_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start Game", callback_data="setup_start_game")],
        [InlineKeyboardButton("⬅️ Back", callback_data="setup_back_to_categories")],
    ])