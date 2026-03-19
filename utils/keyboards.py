from telegram import InlineKeyboardButton, InlineKeyboardMarkup


LEADERBOARD_PAGE_SIZE = 15


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play", callback_data="play_quiz")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("👤 Profile", callback_data="profile")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ])


def back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=callback_data)],
    ])


def back_cancel_keyboard(back_callback: str, cancel_callback: str = "admin_close") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=back_callback)],
        [InlineKeyboardButton("❌ Cancel", callback_data=cancel_callback)],
    ])


def leaderboard_menu_keyboard(chat_type: str) -> InlineKeyboardMarkup:
    if chat_type == "private":
        keyboard = [
            [InlineKeyboardButton("🌍 All-Time", callback_data="lb_global_0")],
            [InlineKeyboardButton("📅 Daily", callback_data="lb_daily_0")],
            [InlineKeyboardButton("📊 Weekly", callback_data="lb_weekly_0")],
            [InlineKeyboardButton("🗓 Monthly", callback_data="lb_monthly_0")],
            [InlineKeyboardButton("🪪 My Rank", callback_data="lb_myrank")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("👥 This Group", callback_data="lb_group_0")],
            [InlineKeyboardButton("🌍 All-Time", callback_data="lb_global_0")],
            [InlineKeyboardButton("📅 Daily", callback_data="lb_daily_0")],
            [InlineKeyboardButton("📊 Weekly", callback_data="lb_weekly_0")],
            [InlineKeyboardButton("🗓 Monthly", callback_data="lb_monthly_0")],
            [InlineKeyboardButton("🪪 My Rank", callback_data="lb_myrank")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")],
        ]

    return InlineKeyboardMarkup(keyboard)


def leaderboard_pagination_keyboard(kind: str, offset: int, has_next: bool) -> InlineKeyboardMarkup:
    rows = []
    nav_row = []

    if offset > 0:
        prev_offset = max(0, offset - LEADERBOARD_PAGE_SIZE)
        nav_row.append(
            InlineKeyboardButton("⬅️ Previous", callback_data=f"lb_{kind}_{prev_offset}")
        )

    if has_next:
        next_offset = offset + LEADERBOARD_PAGE_SIZE
        nav_row.append(
            InlineKeyboardButton("➡️ Next", callback_data=f"lb_{kind}_{next_offset}")
        )

    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_leaderboard")])
    return InlineKeyboardMarkup(rows)


# ---------------- ADMIN ---------------- #

def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Questions", callback_data="admin_questions")],
        [InlineKeyboardButton("📊 Stats", callback_data="admin_botstats")],
        [InlineKeyboardButton("📣 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📥 Import CSV", callback_data="admin_import_questions")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])


def admin_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add", callback_data="admin_add_question")],
        [InlineKeyboardButton("✏️ Edit", callback_data="admin_edit_question")],
        [InlineKeyboardButton("🔎 Search", callback_data="admin_search_questions")],
        [InlineKeyboardButton("🗑 Delete", callback_data="admin_delete_question")],
        [InlineKeyboardButton("📋 Latest", callback_data="admin_list_questions")],
        [InlineKeyboardButton("📤 Export CSV", callback_data="admin_export_questions")],
        [InlineKeyboardButton("📥 Import CSV", callback_data="admin_import_questions")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ])


def delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Delete", callback_data="confirm_delete_yes"),
            InlineKeyboardButton("❌ Keep", callback_data="confirm_delete_no"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_close")],
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send", callback_data="broadcast_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_no"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ])


def question_action_keyboard(qid: int, is_active: int, source: str = "questions") -> InlineKeyboardMarkup:
    toggle_label = "🚫 Disable" if is_active else "✅ Enable"
    toggle_action = "deactivate" if is_active else "activate"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"admin_edit_direct_{qid}"),
            InlineKeyboardButton(toggle_label, callback_data=f"admin_toggle_{toggle_action}_{qid}_{source}"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"admin_return_{source}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_close")],
    ])


def search_results_keyboard(results) -> InlineKeyboardMarkup:
    keyboard = []

    for q in results:
        qid = q[0]
        is_active = q[9]

        toggle_label = "🚫 Disable" if is_active else "✅ Enable"
        toggle_action = "deactivate" if is_active else "activate"

        keyboard.append([
            InlineKeyboardButton(f"✏️ Edit {qid}", callback_data=f"admin_search_edit_{qid}"),
            InlineKeyboardButton(toggle_label, callback_data=f"admin_toggle_{toggle_action}_{qid}_search"),
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_close")])

    return InlineKeyboardMarkup(keyboard)


def questions_pagination_keyboard(offset: int, total: int, limit: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + limit - 1) // limit)
    current_page = (offset // limit) + 1

    row = []

    if offset > 0:
        prev_offset = max(0, offset - limit)
        row.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_list_{prev_offset}")
        )

    row.append(
        InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="admin_page_info")
    )

    if offset + limit < total:
        next_offset = offset + limit
        row.append(
            InlineKeyboardButton("➡️ Next", callback_data=f"admin_list_{next_offset}")
        )

    keyboard = [row]
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_close")])

    return InlineKeyboardMarkup(keyboard)