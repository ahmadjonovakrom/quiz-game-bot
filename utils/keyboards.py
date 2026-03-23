from telegram import InlineKeyboardButton, InlineKeyboardMarkup


LEADERBOARD_PAGE_SIZE = 10
FINAL_RESULTS_PAGE_SIZE = 10


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


from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def final_results_keyboard(game_id: int, page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows = []

    # 🔁 MAIN ACTION BUTTONS (your design)
    rows.append([InlineKeyboardButton("🍋 Play Again", callback_data="menu_play")])
    rows.append([InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")])
    rows.append([InlineKeyboardButton("🏠 Menu", callback_data="menu_main")])

    # 📄 NAVIGATION (keep this for pagination)
    nav_row = []

    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                "⬅️ Prev",
                callback_data=f"final_results:{game_id}:{page - 1}",
            )
        )

    if has_next:
        nav_row.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=f"final_results:{game_id}:{page + 1}",
            )
        )

    if nav_row:
        rows.append(nav_row)

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
        [InlineKeyboardButton("📚 Manage Questions", callback_data="admin_questions")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📥 Import Questions", callback_data="admin_import_questions")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_botstats")],
        [InlineKeyboardButton("⚠️ Danger Zone", callback_data="admin_danger_zone")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])


def admin_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Latest Questions", callback_data="admin_list_questions")],
        [InlineKeyboardButton("🔍 Search Questions", callback_data="admin_search_questions")],
        [InlineKeyboardButton("✏️ Edit Question", callback_data="admin_edit_question")],
        [InlineKeyboardButton("🗑 Delete Question", callback_data="admin_delete_question")],
        [InlineKeyboardButton("📤 Export CSV", callback_data="admin_export_questions")],
        [InlineKeyboardButton("📊 Question Stats", callback_data="admin_question_stats")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ])


def delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data="confirm_delete_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="confirm_delete_no"),
        ]
    ])

def admin_reset_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Reset", callback_data="admin_reset_stats_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="admin_danger_zone"),
        ]
    ])

def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send", callback_data="broadcast_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_no"),
        ]
    ])

def admin_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Min Players", callback_data="settings_min_players")],
        [InlineKeyboardButton("⏱ Join Time", callback_data="settings_join_seconds")],
        [InlineKeyboardButton("❓ Question Time", callback_data="settings_question_seconds")],
        [InlineKeyboardButton("⚡ Speed Bonus Time", callback_data="settings_speed_bonus_seconds")],
        [InlineKeyboardButton("🍋 Easy Points", callback_data="settings_points_easy")],
        [InlineKeyboardButton("🍋 Medium Points", callback_data="settings_points_medium")],
        [InlineKeyboardButton("🍋 Hard Points", callback_data="settings_points_hard")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ])

def question_action_keyboard(
    question_id: int,
    is_active: bool = True,
    source: str = "questions",
) -> InlineKeyboardMarkup:
    toggle_action = "deactivate" if is_active else "activate"
    toggle_text = "🚫 Deactivate" if is_active else "✅ Activate"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"admin_edit_direct_{question_id}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"admin_delete_direct_{question_id}"),
        ],
        [
            InlineKeyboardButton(
                toggle_text,
                callback_data=f"admin_toggle_{toggle_action}_{question_id}_{source}",
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data=f"admin_return_{source}",
            )
        ],
    ])


def questions_pagination_keyboard(
    offset: int,
    total: int,
    limit: int,
) -> InlineKeyboardMarkup:
    rows = []
    nav = []

    prev_offset = max(0, offset - limit)
    next_offset = offset + limit

    if offset > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_list_{prev_offset}"))

    if next_offset < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_list_{next_offset}"))

    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")])
    return InlineKeyboardMarkup(rows)


def search_results_keyboard(results) -> InlineKeyboardMarkup:
    rows = []

    for q in results[:10]:
        qid = q[0]
        rows.append([
            InlineKeyboardButton(
                f"Question #{qid}",
                callback_data=f"admin_open_{qid}",
            )
        ])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")])
    return InlineKeyboardMarkup(rows)

def admin_danger_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♻️ Reset Stats", callback_data="admin_reset_stats_confirm")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ])

def edit_question_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Text", callback_data="edit_field_text")],
        [InlineKeyboardButton("🔘 Edit Options", callback_data="edit_field_options")],
        [InlineKeyboardButton("✅ Edit Correct Answer", callback_data="edit_field_correct")],
        [InlineKeyboardButton("🏷 Edit Category", callback_data="edit_field_category")],
        [InlineKeyboardButton("📈 Edit Difficulty", callback_data="edit_field_difficulty")],
        [InlineKeyboardButton("👀 Preview", callback_data="edit_preview")],
        [InlineKeyboardButton("💾 Save", callback_data="edit_save")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")],
    ])


def edit_options_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("A", callback_data="edit_option_a"),
            InlineKeyboardButton("B", callback_data="edit_option_b"),
        ],
        [
            InlineKeyboardButton("C", callback_data="edit_option_c"),
            InlineKeyboardButton("D", callback_data="edit_option_d"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="edit_back_menu")],
    ])