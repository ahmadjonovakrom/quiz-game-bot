from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from utils.helpers import is_admin
from database import (
    add_question,
    get_all_questions,
    get_question_by_id,
    update_question,
    delete_question,
    get_broadcast_chat_ids,
    get_total_users_count,
    get_total_questions_count,
    get_total_games,
    get_total_groups,
)

QUESTION, A, B, C, D, CORRECT = range(6)
DELETE_ID, DELETE_CONFIRM = range(6, 8)
EDIT_ID, EDIT_QUESTION, EDIT_A, EDIT_B, EDIT_C, EDIT_D, EDIT_CORRECT = range(8, 15)
BROADCAST_MESSAGE, BROADCAST_CONFIRM = range(15, 17)


def admin_only_text() -> str:
    return "❌ Admin only."


def admin_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📚 Question Management", callback_data="admin_questions")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_botstats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


def questions_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ Add Question", callback_data="admin_add_question")],
        [InlineKeyboardButton("✏️ Edit Question", callback_data="admin_edit_question")],
        [InlineKeyboardButton("🗑 Delete Question", callback_data="admin_delete_question")],
        [InlineKeyboardButton("📋 List Questions", callback_data="admin_list_questions")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("Cancelled.")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        elif update.callback_query:
            await update.callback_query.answer(admin_only_text(), show_alert=True)
        return

    text = "🛠 *Admin Panel*\n\nChoose an action:"
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=admin_main_keyboard(),
            parse_mode="Markdown",
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=admin_main_keyboard(),
            parse_mode="Markdown",
        )


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    if not is_admin(user.id):
        await query.answer(admin_only_text(), show_alert=True)
        return ConversationHandler.END

    await query.answer()
    data = query.data

    if data == "admin_close":
        await query.edit_message_text("Closed.")
        return ConversationHandler.END

    if data == "admin_back":
        await query.edit_message_text(
            "🛠 *Admin Panel*\n\nChoose an action:",
            reply_markup=admin_main_keyboard(),
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    if data == "admin_questions":
        await query.edit_message_text(
            "📚 *Question Management*\n\nChoose an action:",
            reply_markup=questions_keyboard(),
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    if data == "admin_add_question":
        await query.message.reply_text("Send the question text:")
        return QUESTION

    if data == "admin_delete_question":
        await query.message.reply_text("Send the question ID to delete:")
        return DELETE_ID

    if data == "admin_edit_question":
        await query.message.reply_text("Send the question ID to edit:")
        return EDIT_ID

    if data == "admin_list_questions":
        questions = get_all_questions(limit=30)
        if not questions:
            await query.message.reply_text("No questions found.")
            return ConversationHandler.END

        lines = ["📋 *Questions List:*", ""]

        for q in questions:
            qid = q[0]
            question_text = q[1]
            correct_letter = q[6]
            category = q[7]
            difficulty = q[8]
            is_active = q[9]

            status = "✅" if is_active else "🚫"
            lines.append(
                f"{status} ID {qid}: {question_text}\n"
                f"   Correct: {correct_letter} | {category} | {difficulty}"
            )

        await query.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return ConversationHandler.END

    if data == "admin_botstats":
        total_users = get_total_users_count()
        total_questions = get_total_questions_count()
        total_games = get_total_games()
        total_groups = get_total_groups()

        text = (
            "📊 *Bot Stats*\n\n"
            f"👥 Total users: *{total_users}*\n"
            f"👨‍👩‍👧‍👦 Total groups: *{total_groups}*\n"
            f"🎮 Total games: *{total_games}*\n"
            f"❓ Total questions: *{total_questions}*"
        )
        await query.message.reply_text(text, parse_mode="Markdown")
        return ConversationHandler.END

    if data == "admin_broadcast":
        context.user_data.pop("broadcast_source_chat_id", None)
        context.user_data.pop("broadcast_source_message_id", None)
        await query.message.reply_text(
            "📢 Send the message you want to broadcast.\n\n"
            "Supported:\n"
            "• text\n"
            "• photo with caption\n"
            "• video\n"
            "• document\n"
            "• audio / voice\n\n"
            "Then I’ll ask for confirmation."
        )
        return BROADCAST_MESSAGE

    return ConversationHandler.END


async def question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"] = {"question_text": update.message.text}
    await update.message.reply_text("Send option A:")
    return A


async def a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_a"] = update.message.text
    await update.message.reply_text("Send option B:")
    return B


async def b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_b"] = update.message.text
    await update.message.reply_text("Send option C:")
    return C


async def c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_c"] = update.message.text
    await update.message.reply_text("Send option D:")
    return D


async def d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_d"] = update.message.text
    await update.message.reply_text("Send correct option letter (A/B/C/D):")
    return CORRECT


async def correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()
    if correct not in ("A", "B", "C", "D"):
        await update.message.reply_text("Invalid. Send only A, B, C, or D:")
        return CORRECT

    data = context.user_data["new_question"]
    add_question(
        data["question_text"],
        data["option_a"],
        data["option_b"],
        data["option_c"],
        data["option_d"],
        correct,
    )
    context.user_data.clear()
    await update.message.reply_text("✅ Question added successfully.")
    return ConversationHandler.END


async def delete_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Please send a valid numeric question ID.")
        return DELETE_ID

    qid = int(text)
    q = get_question_by_id(qid)
    if not q:
        await update.message.reply_text("Question not found.")
        return ConversationHandler.END

    context.user_data["delete_qid"] = qid
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, delete", callback_data="confirm_delete_yes"),
            InlineKeyboardButton("❌ No", callback_data="confirm_delete_no"),
        ]
    ])

    await update.message.reply_text(
        f"Are you sure you want to delete:\n\nID {q[0]}: {q[1]}",
        reply_markup=keyboard,
    )
    return DELETE_CONFIRM


async def delete_confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_delete_no":
        context.user_data.clear()
        await query.edit_message_text("Deletion cancelled.")
        return ConversationHandler.END

    qid = context.user_data.get("delete_qid")
    if qid:
        delete_question(qid)

    context.user_data.clear()
    await query.edit_message_text("✅ Question deleted successfully.")
    return ConversationHandler.END


async def edit_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Please send a valid numeric question ID.")
        return EDIT_ID

    qid = int(text)
    q = get_question_by_id(qid)
    if not q:
        await update.message.reply_text("Question not found.")
        return ConversationHandler.END

    context.user_data["edit_qid"] = qid
    context.user_data["edit_question"] = {
        "question_text": q[1],
        "option_a": q[2],
        "option_b": q[3],
        "option_c": q[4],
        "option_d": q[5],
        "correct_option": q[6],
    }

    await update.message.reply_text(
        f"Current question:\n{q[1]}\n\nSend new question text:"
    )
    return EDIT_QUESTION


async def edit_question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["question_text"] = update.message.text
    await update.message.reply_text("Send new option A:")
    return EDIT_A


async def edit_a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_a"] = update.message.text
    await update.message.reply_text("Send new option B:")
    return EDIT_B


async def edit_b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_b"] = update.message.text
    await update.message.reply_text("Send new option C:")
    return EDIT_C


async def edit_c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_c"] = update.message.text
    await update.message.reply_text("Send new option D:")
    return EDIT_D


async def edit_d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_d"] = update.message.text
    await update.message.reply_text("Send correct option letter (A/B/C/D):")
    return EDIT_CORRECT


async def edit_correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()
    if correct not in ("A", "B", "C", "D"):
        await update.message.reply_text("Invalid. Send only A, B, C, or D:")
        return EDIT_CORRECT

    qid = context.user_data["edit_qid"]
    data = context.user_data["edit_question"]
    data["correct_option"] = correct

    update_question(
        qid,
        data["question_text"],
        data["option_a"],
        data["option_b"],
        data["option_c"],
        data["option_d"],
        data["correct_option"],
    )

    context.user_data.clear()
    await update.message.reply_text("✅ Question updated successfully.")
    return ConversationHandler.END


async def broadcast_message_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    context.user_data["broadcast_source_chat_id"] = message.chat_id
    context.user_data["broadcast_source_message_id"] = message.message_id

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send", callback_data="broadcast_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_no"),
        ]
    ])

    await update.message.reply_text(
        "📢 Broadcast preview saved.\n\nSend confirmation?",
        reply_markup=keyboard,
    )
    return BROADCAST_CONFIRM


async def broadcast_confirm_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "broadcast_no":
        context.user_data.pop("broadcast_source_chat_id", None)
        context.user_data.pop("broadcast_source_message_id", None)
        await query.edit_message_text("Broadcast cancelled.")
        return ConversationHandler.END

    source_chat_id = context.user_data.get("broadcast_source_chat_id")
    source_message_id = context.user_data.get("broadcast_source_message_id")

    if not source_chat_id or not source_message_id:
        await query.edit_message_text("Broadcast data missing. Please try again.")
        return ConversationHandler.END

    chat_ids = get_broadcast_chat_ids()
    success = 0
    failed = 0

    await query.edit_message_text(f"📡 Broadcasting to {len(chat_ids)} chats...")

    for chat_id in chat_ids:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source_chat_id,
                message_id=source_message_id,
            )
            success += 1
        except Exception:
            failed += 1

    context.user_data.pop("broadcast_source_chat_id", None)
    context.user_data.pop("broadcast_source_message_id", None)

    await query.message.reply_text(
        "✅ Broadcast finished.\n\n"
        f"Delivered: {success}\n"
        f"Failed: {failed}"
    )
    return ConversationHandler.END