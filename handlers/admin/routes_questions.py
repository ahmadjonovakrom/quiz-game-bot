import csv
import io

from database import (
    get_question_by_id,
    get_total_questions_count,
    get_active_question_count,
    get_question_count_by_category,
    get_question_count_by_difficulty,
)
from services.question_service import (
    toggle_question_status_service,
    export_questions_service,
    list_questions_paginated_service,
)
from telegram import InputFile

from utils.keyboards import (
    delete_confirm_keyboard,
    questions_pagination_keyboard,
    admin_questions_keyboard,
)
from utils.texts import (
    format_question_preview,
    format_latest_questions_text,
)

from .questions import nav_keyboard, questions_keyboard, show_search_results
from .states import *


async def handle_question_routes(query, context, update, show_question_details, show_questions_menu, import_questions_entry):
    data = query.data

    if data.startswith("admin_delete_direct_"):
        qid_text = data.replace("admin_delete_direct_", "").strip()
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

        context.user_data["delete_qid"] = qid

        await query.edit_message_text(
            "🗑 Delete Question\n\n"
            f"{format_question_preview(q)}\n\n"
            "Are you sure you want to delete this question?",
            reply_markup=delete_confirm_keyboard(),
        )
        return DELETE_CONFIRM

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

        return None

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

        from utils.keyboards import edit_question_menu_keyboard

        await query.edit_message_text(
            "✏️ Edit Question\n\n"
            f"{format_question_preview(q)}\n\n"
            "Choose what you want to edit:",
            reply_markup=edit_question_menu_keyboard(),
        )
        return ADMIN_MENU

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

    if data == "admin_question_stats":
        total = get_total_questions_count()
        active = get_active_question_count()
        by_category = get_question_count_by_category()
        by_difficulty = get_question_count_by_difficulty()

        text = "📊 Question Stats\n\n"
        text += f"📚 Total: {total}\n"
        text += f"✅ Active: {active}\n"
        text += f"❌ Inactive: {total - active}\n\n"

        text += "📂 By Category:\n"
        for key, value in by_category.items():
            text += f"• {key.title().replace('_', ' ')}: {value}\n"

        text += "\n📈 By Difficulty:\n"
        for key, value in by_difficulty.items():
            text += f"• {key.title()}: {value}\n"

        await query.edit_message_text(
            text,
            reply_markup=admin_questions_keyboard(),
        )
        return ADMIN_MENU

    return None