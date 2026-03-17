from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from utils.helpers import is_admin
from database import (
    add_question,
    get_all_questions,
    get_question_by_id,
    update_question,
    delete_question,
)

QUESTION, A, B, C, D, CORRECT = range(6)
DELETE_ID, DELETE_CONFIRM = range(6, 8)
EDIT_ID, EDIT_QUESTION, EDIT_A, EDIT_B, EDIT_C, EDIT_D, EDIT_CORRECT = range(8, 15)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def add_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("Send the question text.\n\nUse /cancel to stop.")
    return QUESTION


async def question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Question cannot be empty. Send the question text again.")
        return QUESTION

    context.user_data["q"] = text
    await update.message.reply_text("Option A:")
    return A


async def a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option A cannot be empty.")
        return A

    context.user_data["a"] = text
    await update.message.reply_text("Option B:")
    return B


async def b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option B cannot be empty.")
        return B

    context.user_data["b"] = text
    await update.message.reply_text("Option C:")
    return C


async def c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option C cannot be empty.")
        return C

    context.user_data["c"] = text
    await update.message.reply_text("Option D:")
    return D


async def d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option D cannot be empty.")
        return D

    context.user_data["d"] = text
    await update.message.reply_text("Correct option (A/B/C/D):")
    return CORRECT


async def correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()

    if correct not in {"A", "B", "C", "D"}:
        await update.message.reply_text("Please send only A, B, C, or D.")
        return CORRECT

    q = context.user_data["q"]
    a = context.user_data["a"]
    b = context.user_data["b"]
    c = context.user_data["c"]
    d = context.user_data["d"]

    add_question(q, a, b, c, d, correct)

    preview = (
        "✅ Question added.\n\n"
        f"Q: {q}\n"
        f"A) {a}\n"
        f"B) {b}\n"
        f"C) {c}\n"
        f"D) {d}\n"
        f"Correct: {correct}"
    )

    context.user_data.clear()
    await update.message.reply_text(preview)
    return ConversationHandler.END


async def questions_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_all_questions(limit=50)

    if not rows:
        await update.message.reply_text("No questions saved yet.")
        return

    chunks = []
    current = "📚 Saved Questions\n\n"

    for row in rows:
        block = (
            f"ID: {row[0]}\n"
            f"Q: {row[1]}\n"
            f"A) {row[2]}\n"
            f"B) {row[3]}\n"
            f"C) {row[4]}\n"
            f"D) {row[5]}\n"
            f"Correct: {row[6]}\n\n"
        )

        if len(current) + len(block) > 3500:
            chunks.append(current)
            current = block
        else:
            current += block

    if current.strip():
        chunks.append(current)

    for chunk in chunks:
        await update.message.reply_text(chunk)


async def delete_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("Send question ID to delete.\n\nUse /cancel to stop.")
    return DELETE_ID


async def delete_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text("Please send a valid numeric question ID.")
        return DELETE_ID

    qid = int(text)
    row = get_question_by_id(qid)

    if not row:
        await update.message.reply_text("Question not found. Send another ID or use /cancel.")
        return DELETE_ID

    context.user_data["delete_id"] = qid

    preview = (
        f"⚠️ Delete this question?\n\n"
        f"ID: {row[0]}\n"
        f"Q: {row[1]}\n"
        f"A) {row[2]}\n"
        f"B) {row[3]}\n"
        f"C) {row[4]}\n"
        f"D) {row[5]}\n"
        f"Correct: {row[6]}\n\n"
        f"Reply with YES to confirm or NO to cancel."
    )

    await update.message.reply_text(preview)
    return DELETE_CONFIRM


async def delete_confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()

    if text == "NO":
        context.user_data.clear()
        await update.message.reply_text("Deletion cancelled.")
        return ConversationHandler.END

    if text != "YES":
        await update.message.reply_text("Please reply with YES or NO.")
        return DELETE_CONFIRM

    qid = context.user_data.get("delete_id")
    deleted = delete_question(qid)

    context.user_data.clear()

    if deleted:
        await update.message.reply_text("Question deleted.")
    else:
        await update.message.reply_text("Question not found.")

    return ConversationHandler.END


async def edit_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("Send question ID to edit.\n\nUse /cancel to stop.")
    return EDIT_ID


async def edit_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text("Please send a valid numeric question ID.")
        return EDIT_ID

    qid = int(text)
    row = get_question_by_id(qid)

    if not row:
        await update.message.reply_text("Question not found. Send another ID or use /cancel.")
        return EDIT_ID

    context.user_data["edit_id"] = qid

    await update.message.reply_text(
        "Current question:\n\n"
        f"Q: {row[1]}\n"
        f"A) {row[2]}\n"
        f"B) {row[3]}\n"
        f"C) {row[4]}\n"
        f"D) {row[5]}\n"
        f"Correct: {row[6]}\n\n"
        "Send the new question text:"
    )
    return EDIT_QUESTION


async def edit_question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Question cannot be empty.")
        return EDIT_QUESTION

    context.user_data["q"] = text
    await update.message.reply_text("New Option A:")
    return EDIT_A


async def edit_a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option A cannot be empty.")
        return EDIT_A

    context.user_data["a"] = text
    await update.message.reply_text("New Option B:")
    return EDIT_B


async def edit_b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option B cannot be empty.")
        return EDIT_B

    context.user_data["b"] = text
    await update.message.reply_text("New Option C:")
    return EDIT_C


async def edit_c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option C cannot be empty.")
        return EDIT_C

    context.user_data["c"] = text
    await update.message.reply_text("New Option D:")
    return EDIT_D


async def edit_d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option D cannot be empty.")
        return EDIT_D

    context.user_data["d"] = text
    await update.message.reply_text("Correct option (A/B/C/D):")
    return EDIT_CORRECT


async def edit_correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()

    if correct not in {"A", "B", "C", "D"}:
        await update.message.reply_text("Please send only A, B, C, or D.")
        return EDIT_CORRECT

    qid = context.user_data["edit_id"]
    q = context.user_data["q"]
    a = context.user_data["a"]
    b = context.user_data["b"]
    c = context.user_data["c"]
    d = context.user_data["d"]

    updated = update_question(qid, q, a, b, c, d, correct)

    context.user_data.clear()

    if not updated:
        await update.message.reply_text("Question not found.")
        return ConversationHandler.END

    preview = (
        f"✅ Question {qid} updated.\n\n"
        f"Q: {q}\n"
        f"A) {a}\n"
        f"B) {b}\n"
        f"C) {c}\n"
        f"D) {d}\n"
        f"Correct: {correct}"
    )
    await update.message.reply_text(preview)
    return ConversationHandler.END