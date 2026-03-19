import csv
import io

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import ContextTypes, ConversationHandler

from config import ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES
from utils.helpers import is_admin
from utils.keyboards import (
    admin_main_keyboard,
    admin_questions_keyboard,
    back_cancel_keyboard,
    broadcast_confirm_keyboard,
    delete_confirm_keyboard,
    question_action_keyboard,
    questions_pagination_keyboard,
    search_results_keyboard,
)
from utils.texts import (
    admin_only_text,
    format_admin_panel_text,
    format_bot_stats_text,
    format_import_help_text,
    format_latest_questions_text,
    format_question_details_text,
    format_question_preview,
    format_questions_menu_text,
    format_search_results_text,
)
from database import get_question_by_id, get_conn

from services.question_service import (
    create_question_service,
    list_questions_service,
    list_questions_paginated_service,
    update_question_service,
    delete_question_service,
    toggle_question_status_service,
    search_questions_service,
    export_questions_service,
    import_questions_from_csv_service,
)
from services.stats_service import get_bot_stats_service
from services.broadcast_service import broadcast_copied_message_service

ADMIN_MENU, QUESTION, A, B, C, D, CORRECT = range(7)
DELETE_ID, DELETE_CONFIRM = range(7, 9)
EDIT_ID, EDIT_QUESTION, EDIT_A, EDIT_B, EDIT_C, EDIT_D, EDIT_CORRECT, EDIT_CATEGORY, EDIT_DIFFICULTY = range(9, 18)
BROADCAST_MESSAGE, BROADCAST_CONFIRM = range(18, 20)
IMPORT_FILE = 20
SEARCH_KEYWORD = 21


def nav_keyboard(back_callback: str = "admin_back") -> InlineKeyboardMarkup:
    return back_cancel_keyboard(back_callback)


def questions_keyboard() -> InlineKeyboardMarkup:
    return admin_questions_keyboard()


async def show_question_details(target, qid: int, source: str = "questions"):
    q = get_question_by_id(qid)
    if not q:
        if hasattr(target, "edit_message_text"):
            await target.edit_message_text(
                "Question not found.",
                reply_markup=nav_keyboard("admin_questions"),
            )
        else:
            await target.reply_text(
                "Question not found.",
                reply_markup=nav_keyboard("admin_questions"),
            )
        return ADMIN_MENU

    text = format_question_details_text(q)
    markup = question_action_keyboard(qid, q[9], source)

    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(text, reply_markup=markup)
    else:
        await target.reply_text(text, reply_markup=markup)

    return ADMIN_MENU


async def show_admin_panel_message(target):
    await target.edit_message_text(
        format_admin_panel_text(),
        reply_markup=admin_main_keyboard(),
    )
    return ADMIN_MENU


async def show_questions_menu(target):
    await target.edit_message_text(
        format_questions_menu_text(),
        reply_markup=questions_keyboard(),
    )
    return ADMIN_MENU


async def show_search_results(target, keyword: str):
    result = search_questions_service(keyword, limit=15)

    if not result["ok"]:
        text = result["message"]
        markup = nav_keyboard("admin_questions")

        if hasattr(target, "edit_message_text"):
            await target.edit_message_text(text, reply_markup=markup)
        else:
            await target.reply_text(text, reply_markup=markup)
        return ADMIN_MENU

    results = result["results"]
    keyword = result["keyword"]

    text = format_search_results_text(keyword, results)
    markup = search_results_keyboard(results) if results else nav_keyboard("admin_questions")

    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(text, reply_markup=markup)
    else:
        await target.reply_text(text, reply_markup=markup)

    return ADMIN_MENU


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        elif update.callback_query:
            await update.callback_query.answer(admin_only_text(), show_alert=True)
        return ConversationHandler.END

    text = format_admin_panel_text()

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=admin_main_keyboard(),
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=admin_main_keyboard(),
        )

    return ADMIN_MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    if update.message:
        await update.message.reply_text(
            "Cancelled.",
            reply_markup=admin_main_keyboard(),
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            format_admin_panel_text(),
            reply_markup=admin_main_keyboard(),
        )

    return ConversationHandler.END


async def bot_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.effective_message.reply_text(admin_only_text())
        return

    stats = get_bot_stats_service()
    text = format_bot_stats_text(stats)

    await update.effective_message.reply_text(text)


async def reset_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_admin(user.id):
        await update.effective_message.reply_text(admin_only_text())
        return

    try:
        with get_conn() as conn:
            table_rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row[0] for row in table_rows}

            if "players" in table_names:
                conn.execute(
                    "UPDATE players SET points = 0, games_played = 0, games_won = 0"
                )

            if "games" in table_names:
                conn.execute("DELETE FROM games")

            if "game_results" in table_names:
                conn.execute("DELETE FROM game_results")

            if "answers" in table_names:
                conn.execute("DELETE FROM answers")

            if "group_stats" in table_names:
                conn.execute(
                    "UPDATE group_stats SET points = 0, games_played = 0, games_won = 0"
                )

        await update.effective_message.reply_text(
            "✅ Stats reset completed."
        )

    except Exception as e:
        await update.effective_message.reply_text(
            f"❌ Reset failed: {e}"
        )


async def import_questions_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        elif update.callback_query:
            await update.callback_query.answer(admin_only_text(), show_alert=True)
        return ConversationHandler.END

    text = format_import_help_text(ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES)

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=nav_keyboard(),
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=nav_keyboard(),
        )

    return IMPORT_FILE


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    if not is_admin(user.id):
        await query.answer(admin_only_text(), show_alert=True)
        return ConversationHandler.END

    await query.answer()
    data = query.data

    if data.startswith("admin_edit_direct_"):
        qid_text = data.replace("admin_edit_direct_", "").strip()
        if not qid_text.isdigit():
            await query.edit_message_text(
                "Invalid question ID.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        qid = int(qid_text)
        q = get_question_by_id(qid)
        if not q:
            await query.edit_message_text(
                "Question not found.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        context.user_data["edit_qid"] = qid
        context.user_data["edit_question"] = {
            "question_text": q[1],
            "option_a": q[2],
            "option_b": q[3],
            "option_c": q[4],
            "option_d": q[5],
            "correct_option": q[6],
            "category": q[7],
            "difficulty": q[8],
        }

        await query.edit_message_text(
            "✏️ Edit Question\n\n"
            f"{format_question_preview(q)}\n\n"
            "Send new question text:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_QUESTION

    if data.startswith("admin_open_"):
        qid_text = data.replace("admin_open_", "").strip()
        if not qid_text.isdigit():
            await query.edit_message_text(
                "Invalid question ID.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        qid = int(qid_text)
        return await show_question_details(query, qid, "questions")

    if data.startswith("admin_toggle_"):
        parts = data.split("_")
        if len(parts) < 5:
            await query.edit_message_text(
                "Invalid action.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        action = parts[2]
        qid_text = parts[3]
        source = parts[4]

        if not qid_text.isdigit():
            await query.edit_message_text(
                "Invalid question ID.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        qid = int(qid_text)
        result = toggle_question_status_service(qid, action)

        if not result["ok"]:
            await query.edit_message_text(
                result["message"],
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        if source == "search":
            keyword = context.user_data.get("search_keyword")
            if keyword:
                return await show_search_results(query, keyword)
            return await show_questions_menu(query)

        return await show_question_details(query, qid, source)

    if data.startswith("admin_return_"):
        source = data.replace("admin_return_", "").strip()

        if source == "search":
            keyword = context.user_data.get("search_keyword")
            if keyword:
                return await show_search_results(query, keyword)

        if source == "questions":
            return await show_questions_menu(query)

        return await show_admin_panel_message(query)

    if data.startswith("admin_search_edit_"):
        qid_text = data.replace("admin_search_edit_", "").strip()
        if not qid_text.isdigit():
            await query.edit_message_text(
                "Invalid question ID.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        qid = int(qid_text)
        q = get_question_by_id(qid)
        if not q:
            keyword = context.user_data.get("search_keyword")
            if keyword:
                return await show_search_results(query, keyword)

            await query.edit_message_text(
                "Question not found.",
                reply_markup=questions_keyboard(),
            )
            return ADMIN_MENU

        context.user_data["edit_qid"] = qid
        context.user_data["edit_question"] = {
            "question_text": q[1],
            "option_a": q[2],
            "option_b": q[3],
            "option_c": q[4],
            "option_d": q[5],
            "correct_option": q[6],
            "category": q[7],
            "difficulty": q[8],
        }

        await query.edit_message_text(
            "✏️ Edit Question\n\n"
            f"{format_question_preview(q)}\n\n"
            "Send new question text:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_QUESTION

    if data == "admin_close":
        context.user_data.clear()
        await query.edit_message_text("Closed.")
        return ConversationHandler.END

    if data == "admin_back":
        context.user_data.clear()
        return await show_admin_panel_message(query)

    if data == "admin_questions":
        context.user_data.clear()
        return await show_questions_menu(query)

    if data == "admin_add_question":
        context.user_data.clear()
        await query.edit_message_text(
            "➕ Add Question (1/6)\n\nSend the question text.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return QUESTION

    if data == "admin_delete_question":
        context.user_data.clear()
        await query.edit_message_text(
            "🗑 Delete Question\n\nSend the question ID to preview it before deletion.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return DELETE_ID

    if data == "admin_edit_question":
        context.user_data.clear()
        await query.edit_message_text(
            "✏️ Edit Question\n\nSend the question ID to edit.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_ID

    if data == "admin_search_questions":
        context.user_data.clear()
        await query.edit_message_text(
            "🔎 Search Questions\n\nSend a keyword to search in question text, options, category, or difficulty.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return SEARCH_KEYWORD

    if data == "admin_export_questions":
        rows = export_questions_service()

        if not rows:
            await query.edit_message_text(
                "📤 Export CSV\n\nNo questions found.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id",
                "question_text",
                "option_a",
                "option_b",
                "option_c",
                "option_d",
                "correct_option",
                "category",
                "difficulty",
                "is_active",
                "times_used",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

        csv_bytes = output.getvalue().encode("utf-8-sig")
        file_obj = io.BytesIO(csv_bytes)
        file_obj.name = "questions_export.csv"

        await query.message.reply_document(
            document=InputFile(file_obj),
            caption=f"📤 Exported {len(rows)} questions.",
        )

        return await show_questions_menu(query)

    if data == "admin_import_questions":
        return await import_questions_entry(update, context)

    if data == "admin_page_info":
        await query.answer()
        return ADMIN_MENU

    if data.startswith("admin_list"):
        if data == "admin_list_questions":
            offset = 0
        else:
            offset_text = data.split("_")[-1]

            if not offset_text.isdigit():
                await query.edit_message_text(
                    "Invalid page.",
                    reply_markup=nav_keyboard("admin_questions"),
                )
                return ADMIN_MENU

            offset = int(offset_text)

        limit = 10

        result = list_questions_paginated_service(limit, offset)
        questions = result["questions"]
        total = result["total"]

        text = format_latest_questions_text(questions)

        if len(text) > 4000:
            text = text[:3900] + "\n\n..."

        await query.edit_message_text(
            text,
            reply_markup=questions_pagination_keyboard(offset, total, limit),
        )
        return ADMIN_MENU

    if data == "admin_botstats":
        stats = get_bot_stats_service()
        text = format_bot_stats_text(stats)

        await query.edit_message_text(
            text,
            reply_markup=nav_keyboard(),
        )
        return ADMIN_MENU

    if data == "admin_broadcast":
        context.user_data.pop("broadcast_source_chat_id", None)
        context.user_data.pop("broadcast_source_message_id", None)

        await query.edit_message_text(
            "📣 Broadcast\n\n"
            "Send the message you want to broadcast.\n\n"
            "Supported:\n"
            "• text\n"
            "• photo with caption\n"
            "• video\n"
            "• document\n"
            "• audio / voice",
            reply_markup=nav_keyboard(),
        )
        return BROADCAST_MESSAGE

    return ADMIN_MENU


async def question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"] = {"question_text": update.message.text}
    await update.message.reply_text(
        "➕ Add Question (2/6)\n\nSend option A.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return A


async def a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_a"] = update.message.text
    await update.message.reply_text(
        "➕ Add Question (3/6)\n\nSend option B.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return B


async def b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_b"] = update.message.text
    await update.message.reply_text(
        "➕ Add Question (4/6)\n\nSend option C.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return C


async def c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_c"] = update.message.text
    await update.message.reply_text(
        "➕ Add Question (5/6)\n\nSend option D.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return D


async def d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_d"] = update.message.text
    await update.message.reply_text(
        "➕ Add Question (6/6)\n\nSend the correct option letter: A, B, C, or D.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return CORRECT


async def correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()
    if correct not in ("A", "B", "C", "D"):
        await update.message.reply_text(
            "Invalid input. Send only A, B, C, or D.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return CORRECT

    data = context.user_data["new_question"]
    data["correct_option"] = correct
    data["category"] = "mixed"
    data["difficulty"] = "easy"
    data["created_by"] = update.effective_user.id

    result = create_question_service(data)
    context.user_data.clear()

    if not result["ok"]:
        await update.message.reply_text(
            result["message"],
            reply_markup=questions_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        result["message"],
        reply_markup=questions_keyboard(),
    )
    return ConversationHandler.END


async def delete_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(
            "Please send a valid numeric question ID.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return DELETE_ID

    qid = int(text)
    q = get_question_by_id(qid)
    if not q:
        await update.message.reply_text(
            "Question not found.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return DELETE_ID

    context.user_data["delete_qid"] = qid

    await update.message.reply_text(
        "🗑 Delete Question\n\n"
        f"{format_question_preview(q)}\n\n"
        "Are you sure you want to delete this question?",
        reply_markup=delete_confirm_keyboard(),
    )
    return DELETE_CONFIRM


async def delete_confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_delete_no":
        context.user_data.pop("delete_qid", None)
        keyword = context.user_data.get("search_keyword")

        if keyword:
            return await show_search_results(query, keyword)

        await query.edit_message_text(
            "Deletion cancelled.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return ADMIN_MENU

    qid = context.user_data.get("delete_qid")
    context.user_data.pop("delete_qid", None)

    if qid:
        result = delete_question_service(qid)
        if not result["ok"]:
            await query.edit_message_text(
                result["message"],
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

    keyword = context.user_data.get("search_keyword")
    if keyword:
        return await show_search_results(query, keyword)

    await query.edit_message_text(
        "✅ Question deleted successfully.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return ADMIN_MENU


async def edit_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(
            "Please send a valid numeric question ID.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_ID

    qid = int(text)
    q = get_question_by_id(qid)
    if not q:
        await update.message.reply_text(
            "Question not found.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_ID

    context.user_data["edit_qid"] = qid
    context.user_data["edit_question"] = {
        "question_text": q[1],
        "option_a": q[2],
        "option_b": q[3],
        "option_c": q[4],
        "option_d": q[5],
        "correct_option": q[6],
        "category": q[7],
        "difficulty": q[8],
    }

    await update.message.reply_text(
        "✏️ Edit Question\n\n"
        f"{format_question_preview(q)}\n\n"
        "Send new question text:",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_QUESTION


async def edit_question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["question_text"] = update.message.text
    await update.message.reply_text(
        "✏️ Edit Question (2/8)\n\nSend new option A.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_A


async def edit_a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_a"] = update.message.text
    await update.message.reply_text(
        "✏️ Edit Question (3/8)\n\nSend new option B.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_B


async def edit_b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_b"] = update.message.text
    await update.message.reply_text(
        "✏️ Edit Question (4/8)\n\nSend new option C.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_C


async def edit_c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_c"] = update.message.text
    await update.message.reply_text(
        "✏️ Edit Question (5/8)\n\nSend new option D.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_D


async def edit_d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_d"] = update.message.text
    await update.message.reply_text(
        "✏️ Edit Question (6/8)\n\nSend the correct option letter: A, B, C, or D.",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_CORRECT


async def edit_correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()
    if correct not in ("A", "B", "C", "D"):
        await update.message.reply_text(
            "Invalid input. Send only A, B, C, or D.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_CORRECT

    context.user_data["edit_question"]["correct_option"] = correct
    await update.message.reply_text(
        "✏️ Edit Question (7/8)\n\nSend new category.\n\n"
        f"Allowed: {', '.join(ALLOWED_CATEGORIES)}",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_CATEGORY


async def edit_category_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text.strip().lower()

    if category not in ALLOWED_CATEGORIES:
        await update.message.reply_text(
            "Invalid category.\n\n"
            f"Allowed: {', '.join(ALLOWED_CATEGORIES)}",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_CATEGORY

    context.user_data["edit_question"]["category"] = category
    await update.message.reply_text(
        "✏️ Edit Question (8/8)\n\nSend new difficulty.\n\n"
        f"Allowed: {', '.join(ALLOWED_DIFFICULTIES)}",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_DIFFICULTY


async def edit_difficulty_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    difficulty = update.message.text.strip().lower()

    if difficulty not in ALLOWED_DIFFICULTIES:
        await update.message.reply_text(
            "Invalid difficulty.\n\n"
            f"Allowed: {', '.join(ALLOWED_DIFFICULTIES)}",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_DIFFICULTY

    qid = context.user_data["edit_qid"]
    data = context.user_data["edit_question"]
    data["difficulty"] = difficulty

    result = update_question_service(qid, data)
    context.user_data.clear()

    await update.message.reply_text(
        result["message"],
        reply_markup=questions_keyboard(),
    )
    return ConversationHandler.END


async def search_keyword_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()

    if not keyword:
        await update.message.reply_text(
            "Please send a keyword.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return SEARCH_KEYWORD

    context.user_data["search_keyword"] = keyword
    return await show_search_results(update.message, keyword)


async def import_questions_file_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if not document:
        await update.message.reply_text(
            "Please send a CSV file.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return IMPORT_FILE

    if not document.file_name or not document.file_name.lower().endswith(".csv"):
        await update.message.reply_text(
            "Please send a valid CSV file ending in .csv",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return IMPORT_FILE

    file = await document.get_file()
    content = await file.download_as_bytearray()

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            await update.message.reply_text(
                "Could not read this CSV file. Please save it as UTF-8 and try again.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return IMPORT_FILE

    result = import_questions_from_csv_service(
        csv_text=text,
        created_by=update.effective_user.id,
    )

    if not result["ok"]:
        await update.message.reply_text(
            result["message"],
            reply_markup=nav_keyboard("admin_questions"),
        )
        return IMPORT_FILE

    context.user_data.clear()

    total_skipped = result["duplicate_skipped"] + result["invalid_skipped"]

    result_text = (
        "📥 Import Finished\n\n"
        f"✅ Imported: {result['imported']}\n"
        f"♻️ Duplicate skipped: {result['duplicate_skipped']}\n"
        f"⚠️ Invalid skipped: {result['invalid_skipped']}\n"
        f"📊 Total skipped: {total_skipped}"
    )

    errors = result["errors"]
    if errors:
        preview = "\n".join(errors[:10])
        result_text += f"\n\nFirst errors:\n{preview}"

        if len(errors) > 10:
            result_text += f"\n\n...and {len(errors) - 10} more."

    await update.message.reply_text(
        result_text,
        reply_markup=questions_keyboard(),
    )
    return ConversationHandler.END


async def broadcast_message_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    context.user_data["broadcast_source_chat_id"] = message.chat_id
    context.user_data["broadcast_source_message_id"] = message.message_id

    await update.message.reply_text(
        "📣 Broadcast preview saved.\n\nSend confirmation?",
        reply_markup=broadcast_confirm_keyboard(),
    )
    return BROADCAST_CONFIRM


async def broadcast_confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "broadcast_no":
        context.user_data.pop("broadcast_source_chat_id", None)
        context.user_data.pop("broadcast_source_message_id", None)
        await query.edit_message_text(
            "Broadcast cancelled.",
            reply_markup=admin_main_keyboard(),
        )
        return ConversationHandler.END

    source_chat_id = context.user_data.get("broadcast_source_chat_id")
    source_message_id = context.user_data.get("broadcast_source_message_id")

    if not source_chat_id or not source_message_id:
        await query.edit_message_text(
            "Broadcast data missing. Please try again.",
            reply_markup=admin_main_keyboard(),
        )
        return ConversationHandler.END

    await query.edit_message_text("📡 Broadcasting...")

    result = await broadcast_copied_message_service(
        bot=context.bot,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
    )

    context.user_data.pop("broadcast_source_chat_id", None)
    context.user_data.pop("broadcast_source_message_id", None)

    await query.message.reply_text(
        "✅ Broadcast finished.\n\n"
        f"Delivered: {result['success']}\n"
        f"Failed: {result['failed']}",
        reply_markup=admin_main_keyboard(),
    )
    return ConversationHandler.END