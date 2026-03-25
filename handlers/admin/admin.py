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
    bot_stats_keyboard,
    bot_groups_keyboard,
    bot_group_details_keyboard,
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
    format_groups_list_text,
    format_group_details_text,
)
from database import (
    get_question_by_id,
    get_conn,
    get_total_questions_count,
    get_active_question_count,
    get_question_count_by_category,
    get_question_count_by_difficulty,
    get_total_games,
    get_total_groups,
    get_total_players,
    get_total_users_count,
    get_all_groups,
    get_group_stats,
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
from .routes_questions import handle_question_routes
from .routes_misc import handle_misc_routes

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


async def bot_stats_command(update, context):
    stats = {
        "total_users": get_total_users_count(),
        "total_players": get_total_players(),
        "total_questions": get_total_questions_count(),
        "total_games": get_total_games(),
        "total_groups": get_total_groups(),
    }

    text = format_bot_stats_text(stats)

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=text,
            reply_markup=bot_stats_keyboard(stats["total_groups"]),
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=bot_stats_keyboard(stats["total_groups"]),
        )


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

    result = await handle_question_routes(
        query,
        context,
        update,
        show_question_details,
        show_questions_menu,
        import_questions_entry,
    )
    if result is not None:
        return result

    result = await handle_misc_routes(
        query,
        context,
        update,
        show_admin_panel_message,
        show_questions_menu,
        reset_stats,
    )
    if result is not None:
        return result

    if data == "admin_botstats":
        stats = {
            "total_users": get_total_users_count(),
            "total_players": get_total_players(),
            "total_questions": get_total_questions_count(),
            "total_games": get_total_games(),
            "total_groups": get_total_groups(),
        }

        await query.edit_message_text(
            text=format_bot_stats_text(stats),
            reply_markup=bot_stats_keyboard(stats["total_groups"]),
        )
        return ADMIN_MENU

    if data == "admin_stats_groups":
        groups = get_all_groups()

        await query.edit_message_text(
            text=format_groups_list_text(groups),
            reply_markup=bot_groups_keyboard(groups),
        )
        return ADMIN_MENU

    if data.startswith("admin_stats_group_"):
        chat_id = int(data.replace("admin_stats_group_", ""))
        group_stats = get_group_stats(chat_id)

        await query.edit_message_text(
            text=format_group_details_text(group_stats),
            reply_markup=bot_group_details_keyboard(),
        )
        return ADMIN_MENU

    if data.startswith("admin_return_"):
        source = data.replace("admin_return_", "").strip()

        if source == "search":
            keyword = context.user_data.get("search_keyword")
            if keyword:
                return await show_search_results(query, keyword)

        if source == "questions":
            return await show_questions_menu(query)

        return await show_admin_panel_message(query)

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