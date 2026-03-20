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


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Question", callback_data="admin_add_question")],
        [InlineKeyboardButton("📚 Manage Questions", callback_data="admin_questions_menu")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📥 Import Questions", callback_data="admin_import_questions")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_bot_stats")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])


def admin_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Latest Questions", callback_data="admin_list_questions")],
        [InlineKeyboardButton("🔍 Search Questions", callback_data="admin_search_questions")],
        [InlineKeyboardButton("✏️ Edit Question", callback_data="admin_edit_question")],
        [InlineKeyboardButton("🗑 Delete Question", callback_data="admin_delete_question")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back_main")],
    ])


def delete_confirm_keyboard(question_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"admin_delete_confirm_{question_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="admin_questions_menu"),
        ]
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send", callback_data="admin_broadcast_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="admin_close"),
        ]
    ])


def question_action_keyboard(question_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    toggle_text = "🚫 Deactivate" if is_active else "✅ Activate"
    toggle_callback = (
        f"admin_deactivate_{question_id}" if is_active else f"admin_activate_{question_id}"
    )

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"admin_edit_{question_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"admin_delete_{question_id}"),
        ],
        [InlineKeyboardButton(toggle_text, callback_data=toggle_callback)],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_questions_menu")],
    ])


def questions_pagination_keyboard(
    page: int,
    has_next: bool,
    prefix: str = "admin_questions_page",
) -> InlineKeyboardMarkup:
    row = []

    if page > 1:
        row.append(
            InlineKeyboardButton(
                "⬅️ Prev",
                callback_data=f"{prefix}:{page - 1}",
            )
        )

    if has_next:
        row.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=f"{prefix}:{page + 1}",
            )
        )

    rows = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions_menu")])
    return InlineKeyboardMarkup(rows)


def search_results_keyboard(question_ids: list[int]) -> InlineKeyboardMarkup:
    rows = []

    for question_id in question_ids[:10]:
        rows.append([
            InlineKeyboardButton(
                f"Question #{question_id}",
                callback_data=f"admin_question_{question_id}",
            )
        ])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions_menu")])
    return InlineKeyboardMarkup(rows)