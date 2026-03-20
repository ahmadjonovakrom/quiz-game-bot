from telegram import InlineKeyboardButton, InlineKeyboardMarkup


LEADERBOARD_PAGE_SIZE = 15


def main_menu_keyboard(chat_type: str = "private") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Quiz", callback_data="menu_play")],
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
    buttons = []

    if chat_type != "private":
        buttons.append([
            InlineKeyboardButton("👥 This Group", callback_data="leaderboard_scope_group"),
            InlineKeyboardButton("🌍 Global", callback_data="leaderboard_scope_global"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton("🌍 Global", callback_data="leaderboard_scope_global"),
        ])

    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data="menu_main"),
    ])

    return InlineKeyboardMarkup(buttons)


def leaderboard_period_keyboard(scope: str, chat_type: str) -> InlineKeyboardMarkup:
    back_target = "leaderboard_menu"

    if scope == "group" and chat_type != "private":
        title_prefix = "group"
    else:
        title_prefix = "global"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏆 All Time", callback_data=f"leaderboard_{title_prefix}_all"),
            InlineKeyboardButton("📅 Daily", callback_data=f"leaderboard_{title_prefix}_daily"),
        ],
        [
            InlineKeyboardButton("📈 Weekly", callback_data=f"leaderboard_{title_prefix}_weekly"),
            InlineKeyboardButton("🗓 Monthly", callback_data=f"leaderboard_{title_prefix}_monthly"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=back_target),
        ],
    ])


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Question Management", callback_data="admin_questions")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_botstats")],
        [InlineKeyboardButton("📣 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])


def admin_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Question", callback_data="admin_add_question")],
        [InlineKeyboardButton("✏️ Edit Question", callback_data="admin_edit_question")],
        [InlineKeyboardButton("🗑️ Delete Question", callback_data="admin_delete_question")],
        [InlineKeyboardButton("🔎 Search Questions", callback_data="admin_search_questions")],
        [InlineKeyboardButton("📄 List Questions", callback_data="admin_list_questions")],
        [InlineKeyboardButton("📤 Export Questions", callback_data="admin_export_questions")],
        [InlineKeyboardButton("📥 Import Questions", callback_data="admin_import_questions")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, send", callback_data="broadcast_yes"),
            InlineKeyboardButton("❌ No", callback_data="broadcast_no"),
        ]
    ])


def delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Delete", callback_data="confirm_delete_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="confirm_delete_no"),
        ]
    ])


def question_action_keyboard(qid: int, is_active: int, source: str = "questions") -> InlineKeyboardMarkup:
    toggle_text = "⏸️ Deactivate" if is_active else "✅ Activate"
    toggle_action = "deactivate" if is_active else "activate"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"admin_edit_direct_{qid}"),
            InlineKeyboardButton(toggle_text, callback_data=f"admin_toggle_{toggle_action}_{qid}_{source}"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"admin_return_{source}"),
        ],
    ])


def questions_pagination_keyboard(
    page: int,
    total_pages: int,
    source: str = "questions",
) -> InlineKeyboardMarkup:
    buttons = []
    nav_row = []

    if page > 1:
        nav_row.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_questions_page_{page - 1}")
        )

    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"admin_questions_page_{page + 1}")
        )

    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"admin_return_{source}")
    ])

    return InlineKeyboardMarkup(buttons)


def search_results_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    nav_row = []

    if page > 1:
        nav_row.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_search_page_{page - 1}")
        )

    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"admin_search_page_{page + 1}")
        )

    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")
    ])

    return InlineKeyboardMarkup(buttons)