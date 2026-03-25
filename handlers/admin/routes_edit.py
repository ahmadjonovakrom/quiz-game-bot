from telegram.ext import ConversationHandler

from config import ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES
from utils.keyboards import edit_question_menu_keyboard, edit_options_keyboard
from utils.texts import format_question_preview
from database import get_question_by_id
from services.question_service import update_question_service

from .questions import nav_keyboard, questions_keyboard
from .states import *


async def handle_edit_routes(query, context):
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
            "Choose what you want to edit:",
            reply_markup=edit_question_menu_keyboard(),
        )
        return ADMIN_MENU

    if data == "admin_edit_question":
        context.user_data.clear()
        await query.edit_message_text(
            "✏️ Edit Question\n\nSend the question ID to edit.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_ID

    if data == "edit_field_text":
        await query.edit_message_text(
            "✏️ Edit Text\n\nSend the new question text:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_TEXT_ONLY

    if data == "edit_field_options":
        await query.edit_message_text(
            "🔘 Edit Options\n\nChoose which option to edit:",
            reply_markup=edit_options_keyboard(),
        )
        return ADMIN_MENU

    if data == "edit_option_a":
        context.user_data["edit_option_target"] = "option_a"
        await query.edit_message_text(
            "🔘 Edit Option A\n\nSend the new text for option A:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_OPTION_ONLY

    if data == "edit_option_b":
        context.user_data["edit_option_target"] = "option_b"
        await query.edit_message_text(
            "🔘 Edit Option B\n\nSend the new text for option B:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_OPTION_ONLY

    if data == "edit_option_c":
        context.user_data["edit_option_target"] = "option_c"
        await query.edit_message_text(
            "🔘 Edit Option C\n\nSend the new text for option C:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_OPTION_ONLY

    if data == "edit_option_d":
        context.user_data["edit_option_target"] = "option_d"
        await query.edit_message_text(
            "🔘 Edit Option D\n\nSend the new text for option D:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_OPTION_ONLY

    if data == "edit_field_correct":
        await query.edit_message_text(
            "✅ Edit Correct Answer\n\nSend A, B, C, or D:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_CORRECT_ONLY

    if data == "edit_field_category":
        await query.edit_message_text(
            "🏷 Edit Category\n\n"
            f"Allowed: {', '.join(ALLOWED_CATEGORIES)}",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_CATEGORY_ONLY

    if data == "edit_field_difficulty":
        await query.edit_message_text(
            "📈 Edit Difficulty\n\n"
            f"Allowed: {', '.join(ALLOWED_DIFFICULTIES)}",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_DIFFICULTY_ONLY

    if data == "edit_preview":
        q = context.user_data.get("edit_question")
        if not q:
            await query.edit_message_text(
                "No question loaded.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        preview_tuple = (
            context.user_data["edit_qid"],
            q["question_text"],
            q["option_a"],
            q["option_b"],
            q["option_c"],
            q["option_d"],
            q["correct_option"],
            q["category"],
            q["difficulty"],
            1,
            0,
        )

        await query.edit_message_text(
            "👁 Preview\n\n"
            f"{format_question_preview(preview_tuple)}",
            reply_markup=edit_question_menu_keyboard(),
        )
        return ADMIN_MENU

    if data == "edit_save":
        qid = context.user_data.get("edit_qid")
        qdata = context.user_data.get("edit_question")

        if not qid or not qdata:
            await query.edit_message_text(
                "No question loaded.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        result = update_question_service(qid, qdata)
        context.user_data.clear()

        await query.edit_message_text(
            result["message"],
            reply_markup=questions_keyboard(),
        )
        return ConversationHandler.END

    if data == "edit_back_menu":
        q = context.user_data.get("edit_question")
        if not q:
            await query.edit_message_text(
                "No question loaded.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        preview_tuple = (
            context.user_data["edit_qid"],
            q["question_text"],
            q["option_a"],
            q["option_b"],
            q["option_c"],
            q["option_d"],
            q["correct_option"],
            q["category"],
            q["difficulty"],
            1,
            0,
        )

        await query.edit_message_text(
            "✏️ Edit Question\n\n"
            f"{format_question_preview(preview_tuple)}\n\n"
            "Choose what you want to edit:",
            reply_markup=edit_question_menu_keyboard(),
        )
        return ADMIN_MENU

    return None