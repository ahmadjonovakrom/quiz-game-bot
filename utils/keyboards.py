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
            InlineKeyboardButton("🌍 Global", callback_data="leaderboard_global"),
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
        [InlineKeyboardButton("➕ Add Question", callback_data="admin_add_question")],
        [InlineKeyboardButton("✏️ Edit Question", callback_data="admin_edit_question")],
        [InlineKeyboardButton("🗑 Delete Question", callback_data="admin_delete_question")],
        [InlineKeyboardButton("🔎 Search Questions", callback_data="admin_search_questions")],
        [InlineKeyboardButton("📋 List Questions", callback_data="admin_list_questions")],
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
    toggle_text = "🚫 Deactivate" if is_active else "✅ Activate"
    toggle_action = "deactivate" if is_active else "activate"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"admin_edit_direct_{qid}"),
            InlineKeyboardButton(toggle_text, callback_data=f"admin_toggle_{toggle_action}_{qid}_{source}"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"admin_return_{source}"),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="admin_close"),
        ],
    ])


def questions_pagination_keyboard(offset: int, total: int, limit: int) -> InlineKeyboardMarkup:
    prev_offset = max(0, offset - limit)
    next_offset = offset + limit

    current_page = (offset // limit) + 1
    total_pages = max(1, (total + limit - 1) // limit)

    row = []

    if offset > 0:
        row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_list_{prev_offset}"))

    row.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="admin_page_info"))

    if next_offset < total:
        row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_list_{next_offset}"))

    keyboard = [row] if row else []

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")])
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="admin_close")])

    return InlineKeyboardMarkup(keyboard)


def search_results_keyboard(results) -> InlineKeyboardMarkup:
    keyboard = []

    for q in results[:15]:
        qid = q[0] if not isinstance(q, dict) else q.get("id")
        question_text = q[1] if not isinstance(q, dict) else q.get("question_text", "")
        short_text = question_text[:45] + "..." if len(question_text) > 45 else question_text

        keyboard.append([
            InlineKeyboardButton(short_text or f"Question {qid}", callback_data=f"admin_open_{qid}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")])
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="admin_close")])

    return InlineKeyboardMarkup(keyboard)