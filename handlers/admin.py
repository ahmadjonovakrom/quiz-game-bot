from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from utils.helpers import is_admin
from database import (
    add_question,
    get_all_questions,
    delete_question,
)

QUESTION, A, B, C, D, CORRECT = range(6)
DELETE_ID = 7


async def add_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("Send the question text:")
    return QUESTION


async def question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"] = update.message.text
    await update.message.reply_text("Option A:")
    return A


async def a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["a"] = update.message.text
    await update.message.reply_text("Option B:")
    return B


async def b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["b"] = update.message.text
    await update.message.reply_text("Option C:")
    return C


async def c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["c"] = update.message.text
    await update.message.reply_text("Option D:")
    return D


async def d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["d"] = update.message.text
    await update.message.reply_text("Correct option (A/B/C/D):")
    return CORRECT


async def correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()

    if correct not in {"A", "B", "C", "D"}:
        await update.message.reply_text("Please send only A, B, C, or D.")
        return CORRECT

    add_question(
        context.user_data["q"],
        context.user_data["a"],
        context.user_data["b"],
        context.user_data["c"],
        context.user_data["d"],
        correct,
    )

    await update.message.reply_text("Question added.")
    return ConversationHandler.END


async def questions_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_all_questions(limit=100)

    if not rows:
        await update.message.reply_text("No questions saved yet.")
        return

    text = "📚 Saved Questions\n\n"

    for row in rows:
        text += f"{row[0]}. {row[1]}\n"

    await update.message.reply_text(text)


async def delete_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    await update.message.reply_text("Send question ID to delete:")
    return DELETE_ID


async def delete_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text("Please send a valid numeric question ID.")
        return DELETE_ID

    qid = int(text)
    deleted = delete_question(qid)

    if deleted:
        await update.message.reply_text("Deleted.")
    else:
        await update.message.reply_text("Not found.")

    return ConversationHandler.END