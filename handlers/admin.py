import csv
import io

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import ContextTypes, ConversationHandler

from config import ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES
from utils.helpers import is_admin
from database import (
    add_question,
    question_exists,
    get_all_questions,
    get_question_by_id,
    update_question,
    delete_question,
    activate_question,
    deactivate_question,
    get_broadcast_chat_ids,
    get_total_users_count,
    get_total_questions_count,
    get_total_games,
    get_total_groups,
)
from database.questions import (
    search_questions_by_keyword,
    export_questions_to_rows,
)

ADMIN_MENU, QUESTION, A, B, C, D, CORRECT = range(7)
DELETE_ID, DELETE_CONFIRM = range(7, 9)
EDIT_ID, EDIT_QUESTION, EDIT_A, EDIT_B, EDIT_C, EDIT_D, EDIT_CORRECT, EDIT_CATEGORY, EDIT_DIFFICULTY = range(9, 18)
BROADCAST_MESSAGE, BROADCAST_CONFIRM = range(18, 20)
IMPORT_FILE = 20
SEARCH_KEYWORD = 21


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
        [InlineKeyboardButton("🔎 Search Questions", callback_data="admin_search_questions")],
        [InlineKeyboardButton("🗑 Delete Question", callback_data="admin_delete_question")],
        [InlineKeyboardButton("📋 List Questions", callback_data="admin_list_questions")],
        [InlineKeyboardButton("📤 Export CSV", callback_data="admin_export_questions")],
        [InlineKeyboardButton("📥 Import CSV", callback_data="admin_import_questions")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def nav_keyboard(back_callback: str = "admin_back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=back_callback)],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_close")],
    ])


def delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, delete", callback_data="confirm_delete_yes"),
            InlineKeyboardButton("❌ No", callback_data="confirm_delete_no"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_close")],
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send", callback_data="broadcast_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_no"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back")],
    ])


def normalize_text(value: str, default: str = "") -> str:
    value = (value or "").strip()
    return value if value else default


def build_question_preview(q: tuple) -> str:
    question_id = q[0]
    question_text = q[1]
    option_a = q[2]
    option_b = q[3]
    option_c = q[4]
    option_d = q[5]
    correct_letter = q[6]
    category = q[7]
    difficulty = q[8]
    is_active = q[9]
    times_used = q[10]

    return (
        f"🆔 ID: {question_id}\n"
        f"📌 Status: {status_text(is_active)}\n"
        f"🏷 Category: {category}\n"
        f"📈 Difficulty: {difficulty}\n"
        f"🔁 Times used: {times_used}\n\n"
        f"❓ {question_text}\n\n"
        f"A) {option_a}\n"
        f"B) {option_b}\n"
        f"C) {option_c}\n"
        f"D) {option_d}\n\n"
        f"✅ Correct: {correct_letter}"
    )


def status_text(is_active: int) -> str:
    return "✅ Active" if is_active else "🚫 Inactive"


def question_action_keyboard(qid: int, is_active: int, source: str = "questions") -> InlineKeyboardMarkup:
    toggle_label = "🚫 Deactivate" if is_active else "♻️ Activate"
    toggle_action = "deactivate" if is_active else "activate"

    keyboard = [
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"admin_edit_direct_{qid}"),
            InlineKeyboardButton(toggle_label, callback_data=f"admin_toggle_{toggle_action}_{qid}_{source}"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"admin_return_{source}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_close")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_search_results_keyboard(results) -> InlineKeyboardMarkup:
    keyboard = []

    for q in results:
        qid = q[0]
        is_active = q[9]

        toggle_label = "🚫 Deactivate" if is_active else "♻️ Activate"
        toggle_action = "deactivate" if is_active else "activate"

        keyboard.append([
            InlineKeyboardButton(f"✏️ Edit {qid}", callback_data=f"admin_search_edit_{qid}"),
            InlineKeyboardButton(toggle_label, callback_data=f"admin_toggle_{toggle_action}_{qid}_search"),
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_close")])

    return InlineKeyboardMarkup(keyboard)


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

    text = (
        "📘 Question Details\n\n"
        f"{build_question_preview(q)}"
    )

    markup = question_action_keyboard(qid, q[9], source)

    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(text, reply_markup=markup)
    else:
        await target.reply_text(text, reply_markup=markup)

    return ADMIN_MENU


async def show_admin_panel_message(target):
    text = "🛠 *Admin Panel*\n\nChoose an action:"
    await target.edit_message_text(
        text,
        reply_markup=admin_main_keyboard(),
        parse_mode="Markdown",
    )
    return ADMIN_MENU


async def show_questions_menu(target):
    text = "📚 *Question Management*\n\nChoose an action:"
    await target.edit_message_text(
        text,
        reply_markup=questions_keyboard(),
        parse_mode="Markdown",
    )
    return ADMIN_MENU

async def show_search_results(target, keyword: str):
    results = search_questions_by_keyword(keyword, limit=15)

    if not results:
        text = f"🔎 Search results for: {keyword}\n\nNo active questions found."
        markup = nav_keyboard("admin_questions")

        if hasattr(target, "edit_message_text"):
            await target.edit_message_text(text, reply_markup=markup)
        else:
            await target.reply_text(text, reply_markup=markup)

        return ADMIN_MENU

    lines = [f"🔎 Search results for: {keyword}", ""]

    for q in results:
        qid = q[0]
        question_text = q[1]
        category = q[7]
        difficulty = q[8]
        times_used = q[10]

        short_question = question_text[:55] + "..." if len(question_text) > 55 else question_text

        lines.append(
            f"✅ ID {qid}: {short_question}\n"
            f"{category} | {difficulty} | used: {times_used}"
        )

    text = "\n\n".join(lines)
    markup = build_search_results_keyboard(results)

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
            "🛠 *Admin Panel*\n\nChoose an action:",
            reply_markup=admin_main_keyboard(),
            parse_mode="Markdown",
        )

    return ConversationHandler.END

async def bot_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.effective_message.reply_text(admin_only_text())
        return

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

    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def import_questions_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        elif update.callback_query:
            await update.callback_query.answer(admin_only_text(), show_alert=True)
        return ConversationHandler.END

    text = (
        "📥 Import Questions from CSV\n\n"
        "Send a CSV file with this header:\n\n"
        "question_text,option_a,option_b,option_c,option_d,correct_option,category,difficulty\n\n"
        "Example:\n"
        "What does rapid mean?,slow,fast,weak,late,B,vocabulary,easy\n\n"
        "Allowed correct_option values:\n"
        "- A / B / C / D\n"
        "- 1 / 2 / 3 / 4\n\n"
        "Allowed category values:\n"
        f"- {', '.join(ALLOWED_CATEGORIES)}\n\n"
        "Allowed difficulty values:\n"
        f"- {', '.join(ALLOWED_DIFFICULTIES)}\n\n"
        "If category is empty, it becomes mixed.\n"
        "If difficulty is empty, it becomes easy."
    )

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
            f"{build_question_preview(q)}\n\n"
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

        if action == "activate":
            activate_question(qid)
        elif action == "deactivate":
            deactivate_question(qid)

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
            f"{build_question_preview(q)}\n\n"
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
            "➕ *Add Question*\n\nSend the question text.",
            reply_markup=nav_keyboard("admin_questions"),
            parse_mode="Markdown",
        )
        return QUESTION

    if data == "admin_delete_question":
        context.user_data.clear()
        await query.edit_message_text(
            "🗑 *Delete Question*\n\nSend the question ID to preview and delete.",
            reply_markup=nav_keyboard("admin_questions"),
            parse_mode="Markdown",
        )
        return DELETE_ID

    if data == "admin_edit_question":
        context.user_data.clear()
        await query.edit_message_text(
            "✏️ *Edit Question*\n\nSend the question ID to edit.",
            reply_markup=nav_keyboard("admin_questions"),
            parse_mode="Markdown",
        )
        return EDIT_ID

    if data == "admin_search_questions":
        context.user_data.clear()
        await query.edit_message_text(
            "🔎 *Search Questions*\n\nSend a keyword to search in questions, options, category, or difficulty.",
            reply_markup=nav_keyboard("admin_questions"),
            parse_mode="Markdown",
        )
        return SEARCH_KEYWORD

    if data == "admin_export_questions":
        rows = export_questions_to_rows()

        if not rows:
            await query.edit_message_text(
                "📤 Export Questions\n\nNo questions found.",
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

    if data == "admin_list_questions":
        questions = get_all_questions(limit=15)

        if not questions:
            await query.edit_message_text(
                "📋 Questions List\n\nNo questions found.",
                reply_markup=nav_keyboard("admin_questions"),
            )
            return ADMIN_MENU

        lines = ["📋 Latest Questions", ""]

        keyboard = []

        for q in questions:
            qid = q[0]
            question_text = q[1]
            category = q[7]
            difficulty = q[8]
            is_active = q[9]

            short_question = question_text[:45] + "..." if len(question_text) > 45 else question_text
            lines.append(
                f"{status_text(is_active)} | ID {qid}\n"
                f"{short_question}\n"
                f"{category} | {difficulty}"
            )

            keyboard.append([
                InlineKeyboardButton(f"📘 Open {qid}", callback_data=f"admin_open_{qid}"),
            ])

        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_questions")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_close")])

        text = "\n\n".join(lines)
        if len(text) > 4000:
            text = text[:3900] + "\n\n..."

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
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
            reply_markup=nav_keyboard(),
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
            "• audio / voice",
            reply_markup=nav_keyboard(),
            parse_mode="Markdown",
        )
        return BROADCAST_MESSAGE

    return ADMIN_MENU


async def question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"] = {"question_text": update.message.text}
    await update.message.reply_text("Send option A:", reply_markup=nav_keyboard("admin_questions"))
    return A


async def a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_a"] = update.message.text
    await update.message.reply_text("Send option B:", reply_markup=nav_keyboard("admin_questions"))
    return B


async def b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_b"] = update.message.text
    await update.message.reply_text("Send option C:", reply_markup=nav_keyboard("admin_questions"))
    return C


async def c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_c"] = update.message.text
    await update.message.reply_text("Send option D:", reply_markup=nav_keyboard("admin_questions"))
    return D


async def d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_question"]["option_d"] = update.message.text
    await update.message.reply_text(
        "Send correct option letter (A/B/C/D):",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return CORRECT


async def correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()
    if correct not in ("A", "B", "C", "D"):
        await update.message.reply_text(
            "Invalid. Send only A, B, C, or D:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return CORRECT

    data = context.user_data["new_question"]

    if question_exists(data["question_text"]):
        context.user_data.clear()
        await update.message.reply_text(
            "⚠️ This question already exists. Skipped.",
            reply_markup=questions_keyboard(),
        )
        return ConversationHandler.END

    add_question(
        data["question_text"],
        data["option_a"],
        data["option_b"],
        data["option_c"],
        data["option_d"],
        correct,
    )
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Question added successfully.",
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
        "🗑 Question preview:\n\n"
        f"{build_question_preview(q)}\n\n"
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
    if qid:
        delete_question(qid)

    context.user_data.pop("delete_qid", None)

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
        "✏️ Current question:\n\n"
        f"{build_question_preview(q)}\n\n"
        "Send new question text:",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_QUESTION


async def edit_question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["question_text"] = update.message.text
    await update.message.reply_text("Send new option A:", reply_markup=nav_keyboard("admin_questions"))
    return EDIT_A


async def edit_a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_a"] = update.message.text
    await update.message.reply_text("Send new option B:", reply_markup=nav_keyboard("admin_questions"))
    return EDIT_B


async def edit_b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_b"] = update.message.text
    await update.message.reply_text("Send new option C:", reply_markup=nav_keyboard("admin_questions"))
    return EDIT_C


async def edit_c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_c"] = update.message.text
    await update.message.reply_text("Send new option D:", reply_markup=nav_keyboard("admin_questions"))
    return EDIT_D


async def edit_d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_question"]["option_d"] = update.message.text
    await update.message.reply_text(
        "Send correct option letter (A/B/C/D):",
        reply_markup=nav_keyboard("admin_questions"),
    )
    return EDIT_CORRECT


async def edit_correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()
    if correct not in ("A", "B", "C", "D"):
        await update.message.reply_text(
            "Invalid. Send only A, B, C, or D:",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return EDIT_CORRECT

    context.user_data["edit_question"]["correct_option"] = correct
    await update.message.reply_text(
        "Send new category:\n\n"
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
        "Send new difficulty:\n\n"
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

    updated = update_question(
        qid,
        data["question_text"],
        data["option_a"],
        data["option_b"],
        data["option_c"],
        data["option_d"],
        data["correct_option"],
        data["category"],
        data["difficulty"],
    )

    context.user_data.clear()

    if not updated:
        await update.message.reply_text(
            "❌ Failed to update question.",
            reply_markup=questions_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ Question updated successfully.",
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
        await update.message.reply_text(
            "CSV file is empty or invalid.",
            reply_markup=nav_keyboard("admin_questions"),
        )
        return IMPORT_FILE

    fieldnames = {name.strip() for name in reader.fieldnames if name}
    missing = required_columns - fieldnames
    if missing:
        await update.message.reply_text(
            "Missing required columns:\n" + "\n".join(sorted(missing)),
            reply_markup=nav_keyboard("admin_questions"),
        )
        return IMPORT_FILE

    imported = 0
    duplicate_skipped = 0
    invalid_skipped = 0
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
                invalid_skipped += 1
                errors.append(f"Row {row_number}: missing required value")
                continue

            if question_exists(question_text):
                duplicate_skipped += 1
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
            invalid_skipped += 1
            errors.append(f"Row {row_number}: {str(e)}")

    context.user_data.clear()

    total_skipped = duplicate_skipped + invalid_skipped

    result_text = (
        f"📥 Import finished\n\n"
        f"✅ Imported: {imported}\n"
        f"♻️ Duplicate skipped: {duplicate_skipped}\n"
        f"⚠️ Invalid skipped: {invalid_skipped}\n"
        f"📊 Total skipped: {total_skipped}"
    )

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
        "📢 Broadcast preview saved.\n\nSend confirmation?",
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
        f"Failed: {failed}",
        reply_markup=admin_main_keyboard(),
    )
    return ConversationHandler.END