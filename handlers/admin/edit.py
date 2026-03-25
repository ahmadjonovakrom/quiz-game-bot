from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES
from utils.keyboards import edit_question_menu_keyboard
from utils.texts import format_question_preview

from database import get_question_by_id
from services.question_service import update_question_service

from .questions import nav_keyboard, questions_keyboard
from .states import *


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
        "Choose what you want to edit:",
        reply_markup=edit_question_menu_keyboard(),
    )
    await update.message.delete()
    return ADMIN_MENU


async def edit_text_only_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["question_text"] = update.message.text

    q = context.user_data["edit_question"]
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

    await update.message.reply_text(
        "✅ Question text updated.\n\n"
        f"{format_question_preview(preview_tuple)}",
        reply_markup=edit_question_menu_keyboard(),
    )
    return ADMIN_MENU


async def edit_option_only_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = context.user_data.get("edit_option_target")
    if not target:
        await update.message.reply_text(
            "No option selected.",
            reply_markup=edit_question_menu_keyboard(),
        )
        return ADMIN_MENU

    context.user_data["edit_question"][target] = update.message.text

    q = context.user_data["edit_question"]
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

    await update.message.reply_text(
        "✅ Option updated.\n\n"
        f"{format_question_preview(preview_tuple)}",
        reply_markup=edit_question_menu_keyboard(),
    )
    return ADMIN_MENU


async def edit_correct_only_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()
    if correct not in ("A", "B", "C", "D"):
        await update.message.reply_text(
            "Invalid input. Send only A, B, C, or D.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_CORRECT_ONLY

    context.user_data["edit_question"]["correct_option"] = correct

    q = context.user_data["edit_question"]
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

    await update.message.reply_text(
        "✅ Correct answer updated.\n\n"
        f"{format_question_preview(preview_tuple)}",
        reply_markup=edit_question_menu_keyboard(),
    )
    return ADMIN_MENU


async def edit_category_only_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text.strip().lower()
    if category not in ALLOWED_CATEGORIES:
        await update.message.reply_text(
            "Invalid category.\n\n"
            f"Allowed: {', '.join(ALLOWED_CATEGORIES)}",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_CATEGORY_ONLY

    context.user_data["edit_question"]["category"] = category

    q = context.user_data["edit_question"]
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

    await update.message.reply_text(
        "✅ Category updated.\n\n"
        f"{format_question_preview(preview_tuple)}",
        reply_markup=edit_question_menu_keyboard(),
    )
    return ADMIN_MENU


async def edit_difficulty_only_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    difficulty = update.message.text.strip().lower()
    if difficulty not in ALLOWED_DIFFICULTIES:
        await update.message.reply_text(
            "Invalid difficulty.\n\n"
            f"Allowed: {', '.join(ALLOWED_DIFFICULTIES)}",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_DIFFICULTY_ONLY

    context.user_data["edit_question"]["difficulty"] = difficulty

    q = context.user_data["edit_question"]
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

    await update.message.reply_text(
        "✅ Difficulty updated.\n\n"
        f"{format_question_preview(preview_tuple)}",
        reply_markup=edit_question_menu_keyboard(),
    )
    return ADMIN_MENU


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