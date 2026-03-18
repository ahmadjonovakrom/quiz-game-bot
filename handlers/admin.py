from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from utils.helpers import is_admin
from database import (
    add_question,
    get_all_questions,
    get_question_by_id,
    update_question,
    delete_question,
    get_total_players,
    get_total_groups,
    get_total_games,
    get_question_count,
    get_broadcast_chat_ids,
)

QUESTION, A, B, C, D, CORRECT = range(6)
DELETE_ID, DELETE_CONFIRM = range(6, 8)
EDIT_ID, EDIT_QUESTION, EDIT_A, EDIT_B, EDIT_C, EDIT_D, EDIT_CORRECT = range(8, 15)
BROADCAST_MESSAGE = 15


def admin_only_text() -> str:
    return "❌ Admin only."


def admin_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📚 Question Management", callback_data="admin_questions")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_botstats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_questions_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📋 View Questions", callback_data="admin_list")],
        [InlineKeyboardButton("➕ Add Question", callback_data="admin_add")],
        [InlineKeyboardButton("✏️ Edit Question", callback_data="admin_edit")],
        [InlineKeyboardButton("🗑 Delete Question", callback_data="admin_delete")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back_main")]
    ])


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("Cancelled.")
    elif update.callback_query:
        await update.callback_query.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        return

    text = (
        "🛠 Admin Panel\n\n"
        "Welcome back, admin.\n"
        "Choose a section below."
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=admin_main_keyboard(),
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=admin_main_keyboard(),
        )


async def send_questions_menu(query):
    await query.edit_message_text(
        "📚 Question Management\n\nChoose an action:",
        reply_markup=admin_questions_keyboard(),
    )


async def send_bot_stats(query):
    total_players = get_total_players()
    total_groups = get_total_groups()
    total_games = get_total_games()
    total_questions = get_question_count()

    text = (
        "📊 Bot Stats\n\n"
        f"👤 Total players: {total_players}\n"
        f"👥 Total groups: {total_groups}\n"
        f"🎮 Total games: {total_games}\n"
        f"❓ Total questions: {total_questions}"
    )

    await query.edit_message_text(
        text,
        reply_markup=admin_back_keyboard(),
    )


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END

    await query.answer()

    if not is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return ConversationHandler.END

    data = query.data or ""

    if data == "admin_back_main":
        await admin_panel(update, context)
        return ConversationHandler.END

    if data == "admin_questions":
        await send_questions_menu(query)
        return ConversationHandler.END

    if data == "admin_add":
        context.user_data.clear()
        await query.message.reply_text("➕ Send the question text.\n\nUse /cancel to stop.")
        return QUESTION

    if data == "admin_list":
        await send_questions_with_buttons(query.message)
        return ConversationHandler.END

    if data == "admin_edit":
        context.user_data.clear()
        await query.message.reply_text("✏️ Send question ID to edit.\n\nUse /cancel to stop.")
        return EDIT_ID

    if data == "admin_delete":
        context.user_data.clear()
        await query.message.reply_text("🗑 Send question ID to delete.\n\nUse /cancel to stop.")
        return DELETE_ID

    if data == "admin_botstats":
        await send_bot_stats(query)
        return ConversationHandler.END

    if data == "admin_broadcast":
        context.user_data.clear()
        await query.edit_message_text(
            "📢 Broadcast\n\n"
            "Send the message you want to broadcast.\n\n"
            "Use /cancel to stop.",
            reply_markup=admin_back_keyboard(),
        )
        return BROADCAST_MESSAGE

    if data.startswith("qedit|"):
        try:
            qid = int(data.split("|")[1])
        except (IndexError, ValueError):
            await query.message.reply_text("Invalid question ID.")
            return ConversationHandler.END

        row = get_question_by_id(qid)
        if not row:
            await query.message.reply_text("Question not found.")
            return ConversationHandler.END

        context.user_data.clear()
        context.user_data["edit_id"] = qid

        await query.message.reply_text(
            "✏️ Current question:\n\n"
            f"Q: {row[1]}\n"
            f"A) {row[2]}\n"
            f"B) {row[3]}\n"
            f"C) {row[4]}\n"
            f"D) {row[5]}\n"
            f"Correct: {row[6]}\n\n"
            "Send the new question text:"
        )
        return EDIT_QUESTION

    if data.startswith("qdelete|"):
        try:
            qid = int(data.split("|")[1])
        except (IndexError, ValueError):
            await query.message.reply_text("Invalid question ID.")
            return ConversationHandler.END

        row = get_question_by_id(qid)
        if not row:
            await query.message.reply_text("Question not found.")
            return ConversationHandler.END

        context.user_data.clear()
        context.user_data["delete_id"] = qid

        preview = (
            "⚠️ Delete this question?\n\n"
            f"ID: {row[0]}\n"
            f"Q: {row[1]}\n"
            f"A) {row[2]}\n"
            f"B) {row[3]}\n"
            f"C) {row[4]}\n"
            f"D) {row[5]}\n"
            f"Correct: {row[6]}\n\n"
            "Reply with YES to confirm or NO to cancel."
        )

        await query.message.reply_text(preview)
        return DELETE_CONFIRM

    return ConversationHandler.END


async def send_questions_with_buttons(message):
    rows = get_all_questions(limit=50)

    if not rows:
        await message.reply_text("No questions saved yet.")
        return

    await message.reply_text(f"📋 Showing {len(rows)} question(s):")

    for row in rows:
        text = (
            f"ID: {row[0]}\n"
            f"Q: {row[1]}\n"
            f"A) {row[2]}\n"
            f"B) {row[3]}\n"
            f"C) {row[4]}\n"
            f"D) {row[5]}\n"
            f"Correct: {row[6]}"
        )

        keyboard = [[
            InlineKeyboardButton("✏️ Edit", callback_data=f"qedit|{row[0]}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"qdelete|{row[0]}"),
        ]]

        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def add_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("➕ Send the question text.\n\nUse /cancel to stop.")
    return QUESTION


async def question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return QUESTION

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Question cannot be empty. Send the question text again.")
        return QUESTION

    context.user_data["q"] = text
    await update.message.reply_text("Option A:")
    return A


async def a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return A

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option A cannot be empty.")
        return A

    context.user_data["a"] = text
    await update.message.reply_text("Option B:")
    return B


async def b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return B

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option B cannot be empty.")
        return B

    context.user_data["b"] = text
    await update.message.reply_text("Option C:")
    return C


async def c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return C

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option C cannot be empty.")
        return C

    context.user_data["c"] = text
    await update.message.reply_text("Option D:")
    return D


async def d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return D

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option D cannot be empty.")
        return D

    context.user_data["d"] = text
    await update.message.reply_text("Correct option (A/B/C/D):")
    return CORRECT


async def correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return CORRECT

    correct = update.message.text.strip().upper()

    if correct not in {"A", "B", "C", "D"}:
        await update.message.reply_text("Please send only A, B, C, or D.")
        return CORRECT

    q = context.user_data.get("q")
    a = context.user_data.get("a")
    b = context.user_data.get("b")
    c = context.user_data.get("c")
    d = context.user_data.get("d")

    if not all([q, a, b, c, d]):
        context.user_data.clear()
        await update.message.reply_text("Something went wrong. Please start again.")
        return ConversationHandler.END

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
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        return

    if update.message:
        await send_questions_with_buttons(update.message)


async def delete_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("🗑 Send question ID to delete.\n\nUse /cancel to stop.")
    return DELETE_ID


async def delete_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return DELETE_ID

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
        "⚠️ Delete this question?\n\n"
        f"ID: {row[0]}\n"
        f"Q: {row[1]}\n"
        f"A) {row[2]}\n"
        f"B) {row[3]}\n"
        f"C) {row[4]}\n"
        f"D) {row[5]}\n"
        f"Correct: {row[6]}\n\n"
        "Reply with YES to confirm or NO to cancel."
    )

    await update.message.reply_text(preview)
    return DELETE_CONFIRM


async def delete_confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return DELETE_CONFIRM

    text = update.message.text.strip().upper()

    if text == "NO":
        context.user_data.clear()
        await update.message.reply_text("Deletion cancelled.")
        return ConversationHandler.END

    if text != "YES":
        await update.message.reply_text("Please reply with YES or NO.")
        return DELETE_CONFIRM

    qid = context.user_data.get("delete_id")
    if not qid:
        context.user_data.clear()
        await update.message.reply_text("No question selected.")
        return ConversationHandler.END

    deleted = delete_question(qid)
    context.user_data.clear()

    if deleted:
        await update.message.reply_text("✅ Question deleted.")
    else:
        await update.message.reply_text("Question not found.")

    return ConversationHandler.END


async def edit_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("✏️ Send question ID to edit.\n\nUse /cancel to stop.")
    return EDIT_ID


async def edit_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return EDIT_ID

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
        "✏️ Current question:\n\n"
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
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return EDIT_QUESTION

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Question cannot be empty.")
        return EDIT_QUESTION

    context.user_data["q"] = text
    await update.message.reply_text("New Option A:")
    return EDIT_A


async def edit_a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return EDIT_A

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option A cannot be empty.")
        return EDIT_A

    context.user_data["a"] = text
    await update.message.reply_text("New Option B:")
    return EDIT_B


async def edit_b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return EDIT_B

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option B cannot be empty.")
        return EDIT_B

    context.user_data["b"] = text
    await update.message.reply_text("New Option C:")
    return EDIT_C


async def edit_c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return EDIT_C

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option C cannot be empty.")
        return EDIT_C

    context.user_data["c"] = text
    await update.message.reply_text("New Option D:")
    return EDIT_D


async def edit_d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return EDIT_D

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Option D cannot be empty.")
        return EDIT_D

    context.user_data["d"] = text
    await update.message.reply_text("Correct option (A/B/C/D):")
    return EDIT_CORRECT


async def edit_correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return EDIT_CORRECT

    correct = update.message.text.strip().upper()

    if correct not in {"A", "B", "C", "D"}:
        await update.message.reply_text("Please send only A, B, C, or D.")
        return EDIT_CORRECT

    qid = context.user_data.get("edit_id")
    q = context.user_data.get("q")
    a = context.user_data.get("a")
    b = context.user_data.get("b")
    c = context.user_data.get("c")
    d = context.user_data.get("d")

    if not all([qid, q, a, b, c, d]):
        context.user_data.clear()
        await update.message.reply_text("Something went wrong. Please start again.")
        return ConversationHandler.END

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


async def broadcast_message_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        return ConversationHandler.END

    if not update.message or not update.message.text:
        await update.effective_message.reply_text("Send text only.")
        return BROADCAST_MESSAGE

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Broadcast message cannot be empty.")
        return BROADCAST_MESSAGE

    chat_ids = get_broadcast_chat_ids()
    sent = 0
    failed = 0

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        "📢 Broadcast finished.\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )

    context.user_data.clear()
    return ConversationHandler.END