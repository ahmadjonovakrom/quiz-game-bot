from telegram import InlineKeyboardButton, InlineKeyboardMarkup


LEADERBOARD_PAGE_SIZE = 10
FINAL_RESULTS_PAGE_SIZE = 10


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Quiz", callback_data="menu_play")],
        [InlineKeyboardButton("⚔️ Challenge", callback_data="menu_challenge")],
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


def final_results_keyboard(game_id: int, page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows = []

    rows.append([
        InlineKeyboardButton(
            "🍋 Play Again",
            callback_data=f"results_play_again:{game_id}"
        )
    ])

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


def game_setup_questions_keyboard(
    back_callback: str = "menu_main",
) -> InlineKeyboardMarkup:
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
            InlineKeyboardButton("⬅️ Back", callback_data=back_callback),
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


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send", callback_data="broadcast_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_no"),
        ]
    ])


def admin_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    reminder_enabled = bool(settings.get("streak_notify_enabled", 0))
    reminder_hour = int(settings.get("streak_notify_hour", 20))
    reminder_minute = int(settings.get("streak_notify_minute", 0))

    reminder_label = (
        f"🔥 Daily Reminder ({reminder_hour:02d}:{reminder_minute:02d})"
        if reminder_enabled
        else "🔥 Daily Reminder (OFF)"
    )

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"👥 Min Players ({settings.get('min_players', 2)})",
                callback_data="settings_min_players",
            )
        ],
        [
            InlineKeyboardButton(
                f"⏱ Join Time ({settings.get('join_seconds', 90)}s)",
                callback_data="settings_join_seconds",
            )
        ],
        [
            InlineKeyboardButton(
                f"⏱ Question Time ({settings.get('question_seconds', 18)}s)",
                callback_data="settings_question_seconds",
            )
        ],
        [
            InlineKeyboardButton(
                f"⚡ Speed Bonus ({settings.get('speed_bonus_seconds', 5)}s)",
                callback_data="settings_speed_bonus_seconds",
            )
        ],
        [
            InlineKeyboardButton(
                f"🍋 Easy Points ({settings.get('points_easy', 15)})",
                callback_data="settings_points_easy",
            )
        ],
        [
            InlineKeyboardButton(
                f"🍋 Medium Points ({settings.get('points_medium', 25)})",
                callback_data="settings_points_medium",
            )
        ],
        [
            InlineKeyboardButton(
                f"🍋 Hard Points ({settings.get('points_hard', 35)})",
                callback_data="settings_points_hard",
            )
        ],
        [
            InlineKeyboardButton(
                reminder_label,
                callback_data="settings_daily_reminder",
            )
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ])


def settings_value_keyboard(key: str) -> InlineKeyboardMarkup:
    presets = {
        "min_players": [1, 2, 3, 4, 5, 10],
        "join_seconds": [30, 45, 60, 90, 120, 180],
        "question_seconds": [10, 15, 18, 20, 25, 30],
        "speed_bonus_seconds": [3, 5, 7, 10, 12, 15],
        "points_easy": [5, 10, 15, 20, 25, 30],
        "points_medium": [10, 15, 20, 25, 30, 35],
        "points_hard": [15, 20, 25, 35, 40, 50],
    }

    labels = {
        "min_players": "👥 Min Players",
        "join_seconds": "⏱ Join Time",
        "question_seconds": "⏱ Question Time",
        "speed_bonus_seconds": "⚡ Speed Bonus Time",
        "points_easy": "🍋 Easy Points",
        "points_medium": "🍋 Medium Points",
        "points_hard": "🍋 Hard Points",
    }

    values = presets.get(key, [])
    rows = []

    if values:
        row = []
        for value in values:
            suffix = "s" if key in {"join_seconds", "question_seconds", "speed_bonus_seconds"} else ""
            row.append(
                InlineKeyboardButton(
                    f"{value}{suffix}",
                    callback_data=f"settings_value:{key}:{value}",
                )
            )
            if len(row) == 3:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

    title = labels.get(key, key)
    rows.append([InlineKeyboardButton(f"✍️ Type custom {title}", callback_data=f"settings_custom:{key}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_settings")])

    return InlineKeyboardMarkup(rows)


def settings_daily_reminder_keyboard(settings: dict) -> InlineKeyboardMarkup:
    hour = int(settings.get("streak_notify_hour", 20))
    minute = int(settings.get("streak_notify_minute", 0))

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ ON", callback_data="settings_daily_toggle:on"),
            InlineKeyboardButton("⛔ OFF", callback_data="settings_daily_toggle:off"),
        ],
        [
            InlineKeyboardButton("18:00", callback_data="settings_daily_time:18:00"),
            InlineKeyboardButton("20:00", callback_data="settings_daily_time:20:00"),
            InlineKeyboardButton("21:00", callback_data="settings_daily_time:21:00"),
        ],
        [
            InlineKeyboardButton("08:00", callback_data="settings_daily_time:08:00"),
            InlineKeyboardButton("12:00", callback_data="settings_daily_time:12:00"),
            InlineKeyboardButton("22:00", callback_data="settings_daily_time:22:00"),
        ],
        [
            InlineKeyboardButton(
                f"✍️ Type custom time ({hour:02d}:{minute:02d})",
                callback_data="settings_daily_custom",
            )
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_settings")],
    ])


def admin_reset_confirm_keyboard(yes_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Reset", callback_data=yes_callback),
            InlineKeyboardButton("❌ Cancel", callback_data="admin_danger_zone"),
        ]
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
        [InlineKeyboardButton("♻️ Reset All-Time Leaderboard", callback_data="admin_reset_all_time_confirm")],
        [InlineKeyboardButton("💥 Full Reset (All Data)", callback_data="admin_full_reset_confirm")],
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


def bot_stats_keyboard(total_groups: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👥 Groups ({total_groups})", callback_data="admin_stats_groups_page_1")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_close")],
    ])


def bot_groups_keyboard(groups, page: int = 1, per_page: int = 10) -> InlineKeyboardMarkup:
    rows = []

    total = len(groups)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    end = start + per_page
    page_groups = groups[start:end]

    for group in page_groups:
        title = group["title"] or group["username"] or str(group["chat_id"])
        games = group["game_count"] or 0
        prefix = "🟢 " if group["is_active"] else "🔴 "
        safe_title = (f"{prefix}{title} ({games})")[:50]

        rows.append([
            InlineKeyboardButton(
                safe_title,
                callback_data=f"admin_stats_group_{group['chat_id']}_page_{page}"
            )
        ])

    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton("⬅ Prev", callback_data=f"admin_stats_groups_page_{page - 1}")
        )

    nav_row.append(
        InlineKeyboardButton(f"{page}/{total_pages}", callback_data="admin_page_info")
    )

    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Next ➡", callback_data=f"admin_stats_groups_page_{page + 1}")
        )

    rows.append(nav_row)
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_botstats")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_close")])

    return InlineKeyboardMarkup(rows)


def bot_group_details_keyboard(username: str | None = None, page: int = 1) -> InlineKeyboardMarkup:
    rows = []

    if username:
        rows.append([
            InlineKeyboardButton("🔗 Open Group", url=f"https://t.me/{username}")
        ])

    rows.append([
        InlineKeyboardButton("⬅️ Back to Groups", callback_data=f"admin_stats_groups_page_{page}")
    ])
    rows.append([
        InlineKeyboardButton("⬅️ Back to Stats", callback_data="admin_botstats")
    ])
    rows.append([
        InlineKeyboardButton("❌ Cancel", callback_data="admin_close")
    ])

    return InlineKeyboardMarkup(rows)