import csv
import io

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

ADMIN_MENU, QUESTION, A, B, C, D, CORRECT = range(7)
DELETE_ID, DELETE_CONFIRM = range(7, 9)
EDIT_ID, EDIT_QUESTION, EDIT_A, EDIT_B, EDIT_C, EDIT_D, EDIT_CORRECT = range(9, 16)
BROADCAST_MESSAGE, BROADCAST_CONFIRM = range(16, 18)
IMPORT_FILE = 18


def admin_only_text() -> str:
    return "❌ Admin only."


def admin_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📚 Question Management", callback_data="admin_questions")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_botstats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📥 Import Questions", callback_data="admin_import_questions")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


def questions_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ Add Question", callback_data="admin_add_question")],
        [InlineKeyboardButton("✏️ Edit Question", callback_data="admin_edit_question")],
        [InlineKeyboardButton("🗑 Delete Question", callback_data="admin_delete_question")],
        [InlineKeyboardButton("📋 List Questions", callback_data="admin_list_questions")],
        [InlineKeyboardButton("📥 Import CSV", callback_data="admin_import_questions")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]]
    )


def normalize_text(value: str, default: str = "") -> str:
    value = (value or "").strip()
    return value if value else default


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    if update.message:
        await update.message.reply_text("Cancelled.")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "🛠 *Admin Panel*\n\nChoose an action:",
            reply_markup=admin_main_keyboard(),
            parse_mode="Markdown",
        )

    return ConversationHandler.END


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        elif update.callback_query:
            await update.callback_query.answer(admin_only_text(), show_alert=True)
        return ConversationHandler.END

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

    return ADMIN_MENU


async def import_questions_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        elif update.callback_query:
            await update.callback_query.answer(admin_only_text(), show_alert=True)
        return ConversationHandler.END

    text = (
        "📥 *Import Questions from CSV*\n\n"
        "Send a CSV file with this header:\n\n"
        "`question_text,option_a,option_b,option_c,option_d,correct_option,category,difficulty`\n\n"
        "Example:\n"
        "`What does rapid mean?,slow,fast,weak,late,B,vocabulary,easy`\n\n"
        "Allowed correct_option values:\n"
        "• A / B / C / D\n"
        "• 1 / 2 / 3 / 4\n\n"
        "If category is empty, it becomes `mixed`.\n"
        "If difficulty is empty, it becomes `easy`.\n\n"
        "Use /cancel to stop."
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
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

    if data == "admin_close":
        context.user_data.clear()
        await query.edit_message_text("Closed.")
        return ConversationHandler.END

    if data == "admin_back":
        context.user_data.clear()
        await query.edit_message_text(
            "🛠 *Admin Panel*\n\nChoose an action:",
            reply_markup=admin_main_keyboard(),
            parse_mode="Markdown",
        )
        return ADMIN_MENU

    if data == "admin_questions":
        await query.edit_message_text(
            "📚 *Question Management*\n\nChoose an action:",
            reply_markup=questions_keyboard(),
            parse_mode="Markdown",
        )
        return ADMIN_MENU

    if data == "admin_add_question":
        context.user_data.clear()
        await query.edit_message_text(
            "➕ *Add Question*\n\nSend the question text.\n\nUse /cancel to stop.",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return QUESTION

    if data == "admin_delete_question":
        context.user_data.clear()
        await query.edit_message_text(
            "🗑 *Delete Question*\n\nSend the question ID to delete.\n\nUse /cancel to stop.",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return DELETE_ID

    if data == "admin_edit_question":
        context.user_data.clear()
        await query.edit_message_text(
            "✏️ *Edit Question*\n\nSend the question ID to edit.\n\nUse /cancel to stop.",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return EDIT_ID

    if data == "admin_import_questions":
        return await import_questions_entry(update, context)

    if data == "admin_list_questions":
        questions = get_all_questions(limit=30)

        if not questions:
            await query.edit_message_text(
                "📋 Questions List\n\nNo questions found.",
                reply_markup=back_keyboard(),
            )
            return ADMIN_MENU

        lines = ["📋 Questions List", ""]

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
                f"Correct: {correct_letter} | {category} | {difficulty}"
            )

        text = "\n\n".join(lines)
        if len(text) > 4000:
            text = text[:3900] + "\n\n..."

        await query.edit_message_text(
            text,
            reply_markup=back_keyboard(),
        )
        return ADMIN_MENU

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

        await query.edit_message_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return ADMIN_MENU

    if data == "admin_broadcast":
        context.user_data.pop("broadcast_source_chat_id", None)
        context.user_data.pop("broadcast_source_message_id", None)

        await query.edit_message_text(
            "📢 *Broadcast*\n\n"
            "Send the message you want to broadcast.\n\n"
            "Supported:\n"
            "• text\n"
            "• photo with caption\n"
            "• video\n"
            "• document\n"
            "• audio / voice\n\n"
            "Use /cancel to stop.",
            reply_markup=back_keyboard(),
            parse_mode="Markdown",
        )
        return BROADCAST_MESSAGE

    return ADMIN_MENU


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
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes, delete", callback_data="confirm_delete_yes"),
                InlineKeyboardButton("❌ No", callback_data="confirm_delete_no"),
            ]
        ]
    )

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


async def import_questions_file_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if not document:
        await update.message.reply_text("Please send a CSV file.")
        return IMPORT_FILE

    if not document.file_name or not document.file_name.lower().endswith(".csv"):
        await update.message.reply_text("Please send a valid CSV file ending in .csv")
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
                "Could not read this CSV file. Please save it as UTF-8 and try again."
            )
            return IMPORT_FILE

    reader = csv.DictReader(io.StringIO(text))

    required_columns = {
        "question_text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_option",
        "category",
        "difficulty",
    }

    if not reader.fieldnames:
        await update.message.reply_text("CSV file is empty or invalid.")
        return IMPORT_FILE

    fieldnames = {name.strip() for name in reader.fieldnames if name}
    missing = required_columns - fieldnames
    if missing:
        await update.message.reply_text(
            "Missing required columns:\n" + "\n".join(sorted(missing))
        )
        return IMPORT_FILE

    imported = 0
    skipped = 0
    errors = []

    for row_number, row in enumerate(reader, start=2):
        try:
            normalized_row = {(k or "").strip(): v for k, v in row.items()}

            question_text = normalize_text(normalized_row.get("question_text"))
            option_a = normalize_text(normalized_row.get("option_a"))
            option_b = normalize_text(normalized_row.get("option_b"))
            option_c = normalize_text(normalized_row.get("option_c"))
            option_d = normalize_text(normalized_row.get("option_d"))
            correct_option = normalize_text(normalized_row.get("correct_option")).upper()
            category = normalize_text(normalized_row.get("category"), "mixed").lower()
            difficulty = normalize_text(normalized_row.get("difficulty"), "easy").lower()

            if not all([question_text, option_a, option_b, option_c, option_d, correct_option]):
                skipped += 1
                errors.append(f"Row {row_number}: missing required value")
                continue

            add_question(
                question_text=question_text,
                option_a=option_a,
                option_b=option_b,
                option_c=option_c,
                option_d=option_d,
                correct_option=correct_option,
                category=category,
                difficulty=difficulty,
                created_by=update.effective_user.id,
            )
            imported += 1

        except Exception as e:
            skipped += 1
            errors.append(f"Row {row_number}: {str(e)}")

    context.user_data.clear()

    result_text = (
        "📥 *Import finished*\n\n"
        f"✅ Imported: *{imported}*\n"
        f"⚠️ Skipped: *{skipped}*"
    )

    if errors:
        preview = "\n".join(errors[:10]).replace("`", "'")
        result_text += f"\n\n*First errors:*\n`{preview}`"

        if len(errors) > 10:
            result_text += f"\n\n...and {len(errors) - 10} more."

    await update.message.reply_text(result_text, parse_mode="Markdown")
    return ConversationHandler.END


async def broadcast_message_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    context.user_data["broadcast_source_chat_id"] = message.chat_id
    context.user_data["broadcast_source_message_id"] = message.message_id

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Send", callback_data="broadcast_yes"),
                InlineKeyboardButton("❌ Cancel", callback_data="broadcast_no"),
            ]
        ]
    )

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