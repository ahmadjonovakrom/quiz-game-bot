import csv
import io
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import ContextTypes, ConversationHandler

from config import ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES
from utils.helpers import is_admin
from utils.keyboards import (
    admin_main_keyboard,
    admin_questions_keyboard,
    admin_danger_keyboard,          
    admin_reset_confirm_keyboard,
    broadcast_confirm_keyboard,
    edit_question_menu_keyboard,
    edit_options_keyboard,
    delete_confirm_keyboard,
    question_action_keyboard,
    questions_pagination_keyboard,
    admin_settings_keyboard,
)
from utils.texts import (
    admin_only_text,
    format_admin_panel_text,
    format_bot_stats_text,
    format_import_help_text,
    format_latest_questions_text,
    format_question_details_text,
    format_question_preview,
    format_questions_menu_text,
)
from database import (
    get_question_by_id,
    get_conn,
    get_total_questions_count,
    get_active_question_count,
    get_question_count_by_category,
    get_question_count_by_difficulty,
)

from services.question_service import (
    list_questions_paginated_service,
    update_question_service,
    toggle_question_status_service,
    export_questions_service,
)
from services.stats_service import get_bot_stats_service
from services.broadcast_service import broadcast_copied_message_service

from .questions import (
    nav_keyboard,
    questions_keyboard,
    show_search_results,
    question_step,
    a_step,
    b_step,
    c_step,
    d_step,
    correct_step,
    delete_id_step,
    delete_confirm_step,
    search_keyword_step,
    import_questions_file_step,
)
from .states import *
from .routes_edit import handle_edit_routes

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

    text = format_question_details_text(q)
    markup = question_action_keyboard(qid, q[9], source)

    if hasattr(target, "edit_message_text"):
        await target.edit_message_text(text, reply_markup=markup)
    else:
        await target.reply_text(text, reply_markup=markup)

    return ADMIN_MENU


async def show_admin_panel_message(target):
    await target.edit_message_text(
        format_admin_panel_text(),
        reply_markup=admin_main_keyboard(),
    )
    return ADMIN_MENU


async def show_questions_menu(target):
    await target.edit_message_text(
        format_questions_menu_text(),
        reply_markup=questions_keyboard(),
    )
    return ADMIN_MENU


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        elif update.callback_query:
            await update.callback_query.answer(admin_only_text(), show_alert=True)
        return ConversationHandler.END

    text = format_admin_panel_text()

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=admin_main_keyboard(),
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=admin_main_keyboard(),
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
            format_admin_panel_text(),
            reply_markup=admin_main_keyboard(),
        )

    return ConversationHandler.END


async def bot_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.effective_message.reply_text(admin_only_text())
        return

    stats = get_bot_stats_service()
    text = format_bot_stats_text(stats)

    await update.effective_message.reply_text(text)


async def reset_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_admin(user.id):
        await update.effective_message.reply_text(admin_only_text())
        return

    try:
        with get_conn() as conn:
            table_rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row[0] for row in table_rows}

            if "players" in table_names:
                player_columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(players)").fetchall()
                }

                set_parts = []

                if "points" in player_columns:
                    set_parts.append("points = 0")
                if "games_played" in player_columns:
                    set_parts.append("games_played = 0")
                if "games_won" in player_columns:
                    set_parts.append("games_won = 0")
                if "correct_answers" in player_columns:
                    set_parts.append("correct_answers = 0")
                if "wrong_answers" in player_columns:
                    set_parts.append("wrong_answers = 0")
                if "total_points" in player_columns:
                    set_parts.append("total_points = 0")
                if "score" in player_columns:
                    set_parts.append("score = 0")

                if set_parts:
                    conn.execute(f"UPDATE players SET {', '.join(set_parts)}")

            if "group_stats" in table_names:
                group_columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(group_stats)").fetchall()
                }

                set_parts = []

                if "points" in group_columns:
                    set_parts.append("points = 0")
                if "games_played" in group_columns:
                    set_parts.append("games_played = 0")
                if "games_won" in group_columns:
                    set_parts.append("games_won = 0")
                if "correct_answers" in group_columns:
                    set_parts.append("correct_answers = 0")
                if "wrong_answers" in group_columns:
                    set_parts.append("wrong_answers = 0")
                if "total_points" in group_columns:
                    set_parts.append("total_points = 0")
                if "score" in group_columns:
                    set_parts.append("score = 0")

                if set_parts:
                    conn.execute(f"UPDATE group_stats SET {', '.join(set_parts)}")

            for table_name in ["games", "game_results", "answers"]:
                if table_name in table_names:
                    conn.execute(f"DELETE FROM {table_name}")

        await update.effective_message.reply_text("✅ Stats reset completed.")

    except Exception as e:
        await update.effective_message.reply_text(f"❌ Reset failed: {e}")


async def import_questions_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text(admin_only_text())
        elif update.callback_query:
            await update.callback_query.answer(admin_only_text(), show_alert=True)
        return ConversationHandler.END

    text = format_import_help_text(ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES)

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
    result = await handle_edit_routes(query, context)
    if result is not None:
        return result
    
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
            f"{format_question_preview(q)}\n\n"
            "Choose what you want to edit:",
            reply_markup=edit_question_menu_keyboard(),
        )
        return ADMIN_MENU

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

    if data == "admin_botstats":
        stats = get_bot_stats_service()
        text = format_bot_stats_text(stats)

        await query.edit_message_text(
            text,
            reply_markup=nav_keyboard(),
        )
        return ADMIN_MENU

    if data == "admin_settings":
        from database import get_all_settings

        settings = get_all_settings()

        text = "⚙️ Settings\n\n"
        for k, v in settings.items():
            text += f"• {k}: {v}\n"

        await query.edit_message_text(
            text,
            reply_markup=admin_settings_keyboard(),
        )
        return ADMIN_MENU

    if data.startswith("settings_"):
        key = data.replace("settings_", "")

        context.user_data["setting_key"] = key

        await query.edit_message_text(
            f"✏️ Update Setting\n\nSend new value for:\n{key}",
            reply_markup=nav_keyboard("admin_settings"),
        )
        return SETTING_VALUE

    if data == "admin_danger_zone":
        await query.edit_message_text(
         "⚠️ Danger Zone\n\nChoose an action:",
            reply_markup=admin_danger_keyboard(),
        )
        return ADMIN_MENU
    
    if data == "admin_reset_stats_confirm":
        await query.edit_message_text(
        "⚠️ Are you sure you want to reset ALL stats?\n\nThis cannot be undone.",
            reply_markup=admin_reset_confirm_keyboard(),
        )
        return ADMIN_MENU
    
    if data == "admin_reset_stats_yes":
        await reset_stats(update, context)
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

    if data == "admin_broadcast":
        context.user_data.pop("broadcast_source_chat_id", None)
        context.user_data.pop("broadcast_source_message_id", None)

        await query.edit_message_text(
            "📣 Broadcast\n\n"
            "Send the message you want to broadcast.\n\n"
            "Supported:\n"
            "• text\n"
            "• photo with caption\n"
            "• video\n"
            "• document\n"
            "• audio / voice",
            reply_markup=nav_keyboard(),
        )
        return BROADCAST_MESSAGE

    return ADMIN_MENU


async def broadcast_message_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    context.user_data["broadcast_source_chat_id"] = message.chat_id
    context.user_data["broadcast_source_message_id"] = message.message_id

    await update.message.reply_text(
        "📣 Broadcast preview saved.\n\nSend confirmation?",
        reply_markup=broadcast_confirm_keyboard(),
    )
    return BROADCAST_CONFIRM

async def settings_update_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import set_setting

    key = context.user_data.get("setting_key")
    value = update.message.text.strip()

    if not key:
        await update.message.reply_text(
            "No setting selected.",
            reply_markup=admin_main_keyboard(),
        )
        return ConversationHandler.END

    set_setting(key, value)

    await update.message.reply_text(
        f"✅ Updated {key} = {value}",
        reply_markup=admin_main_keyboard(),
    )

    context.user_data.clear()
    return ConversationHandler.END

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

    await query.edit_message_text("📡 Broadcasting...")

    result = await broadcast_copied_message_service(
        bot=context.bot,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
    )

    context.user_data.pop("broadcast_source_chat_id", None)
    context.user_data.pop("broadcast_source_message_id", None)

    await query.message.reply_text(
        "✅ Broadcast finished.\n\n"
        f"Delivered: {result['success']}\n"
        f"Failed: {result['failed']}",
        reply_markup=admin_main_keyboard(),
    )
    return ConversationHandler.END