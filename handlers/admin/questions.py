import io

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from utils.keyboards import (
    back_cancel_keyboard,
    admin_questions_keyboard,
    delete_confirm_keyboard,
    search_results_keyboard,
)
from utils.texts import (
    format_question_preview,
    format_search_results_text,
)

from database import get_question_by_id
from services.question_service import (
    create_question_service,
    delete_question_service,
    search_questions_service,
    import_questions_from_csv_service,
)

from .states import *


def nav_keyboard(back_callback: str = "admin_back") -> InlineKeyboardMarkup:
    return back_cancel_keyboard(back_callback)


def questions_keyboard() -> InlineKeyboardMarkup:
    return admin_questions_keyboard()


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