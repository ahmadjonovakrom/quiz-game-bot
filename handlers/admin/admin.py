import csv
import io

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from config import ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES
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
    get_top_groups,
    recalculate_all_player_wins,
)
from services.question_service import (
    list_questions_paginated_service,
    update_question_service,
    toggle_question_status_service,
    export_questions_service,
)
from services.stats_service import get_bot_stats_service
from services.broadcast_service import broadcast_copied_message_service
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

from handlers.admin_reset import reset_all_time_leaderboard, full_reset_all_data
from handlers.broadcast import broadcast_message_step, broadcast_confirm_step


async def settings_update_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import set_setting, get_all_settings

    key = context.user_data.get("setting_key")
    value = update.message.text.strip()

    if not key:
        await update.message.reply_text(
            "No setting selected.",
            reply_markup=admin_main_keyboard(),
        )
        return ConversationHandler.END

    # 🔥 Special handling for daily reminder
    if key == "daily_reminder":
        value_lower = value.lower()

        if value_lower == "on":
            set_setting("streak_notify_enabled", 1)

            settings = get_all_settings()
            await update.message.reply_text(
                "✅ Daily reminder enabled.\n\n"
                f"Current time: {int(settings.get('streak_notify_hour', 20)):02d}:{int(settings.get('streak_notify_minute', 0)):02d}",
                reply_markup=admin_main_keyboard(),
            )
            context.user_data.clear()
            return ConversationHandler.END

        if value_lower == "off":
            set_setting("streak_notify_enabled", 0)

            await update.message.reply_text(
                "✅ Daily reminder disabled.",
                reply_markup=admin_main_keyboard(),
            )
            context.user_data.clear()
            return ConversationHandler.END

        if ":" in value:
            try:
                hour_str, minute_str = value.split(":", 1)
                hour = int(hour_str)
                minute = int(minute_str)

                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError

                set_setting("streak_notify_hour", hour)
                set_setting("streak_notify_minute", minute)
                set_setting("streak_notify_enabled", 1)

                await update.message.reply_text(
                    f"✅ Daily reminder time updated to {hour:02d}:{minute:02d}.",
                    reply_markup=admin_main_keyboard(),
                )
                context.user_data.clear()
                return ConversationHandler.END

            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid time format.\n\n"
                    "Send:\n"
                    "• on\n"
                    "• off\n"
                    "• or time like 20:00",
                    reply_markup=nav_keyboard("admin_settings"),
                )
                return SETTING_VALUE

        await update.message.reply_text(
            "❌ Invalid input.\n\n"
            "Send:\n"
            "• on\n"
            "• off\n"
            "• or time like 20:00",
            reply_markup=nav_keyboard("admin_settings"),
        )
        return SETTING_VALUE

    # ✅ Validation for numeric settings
    numeric_settings = {
        "min_players": (1, 100),
        "join_seconds": (10, 600),
        "question_seconds": (5, 120),
        "speed_bonus_seconds": (1, 60),
        "points_easy": (1, 1000),
        "points_medium": (1, 1000),
        "points_hard": (1, 1000),
    }

    if key in numeric_settings:
        try:
            num = int(value)
        except ValueError:
            await update.message.reply_text(
                "❌ Please send a valid number.",
                reply_markup=nav_keyboard("admin_settings"),
            )
            return SETTING_VALUE

        min_value, max_value = numeric_settings[key]
        if not (min_value <= num <= max_value):
            await update.message.reply_text(
                f"❌ Value must be between {min_value} and {max_value}.",
                reply_markup=nav_keyboard("admin_settings"),
            )
            return SETTING_VALUE

        set_setting(key, num)

        await update.message.reply_text(
            f"✅ Updated {key} = {num}",
            reply_markup=admin_main_keyboard(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    # fallback
    set_setting(key, value)

    await update.message.reply_text(
        f"✅ Updated {key} = {value}",
        reply_markup=admin_main_keyboard(),
    )

    context.user_data.clear()
    return ConversationHandler.END


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


async def bot_stats_command(update, context):
    stats = {
        "total_users": get_total_users_count(),
        "total_players": get_total_players(),
        "total_questions": get_total_questions_count(),
        "total_games": get_total_games(),
        "total_groups": get_total_groups(),
    }

    top_groups = get_top_groups(limit=5)
    text = format_bot_stats_text(stats, top_groups=top_groups)

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


async def fixwins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_admin(user.id):
        await update.message.reply_text("❌ Admin only")
        return

    try:
        recalculate_all_player_wins()
        await update.message.reply_text("✅ Wins recalculated for ALL users!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


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
        reset_all_time_leaderboard,
        full_reset_all_data,
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

        top_groups = get_top_groups(limit=5)

        await query.edit_message_text(
            text=format_bot_stats_text(stats, top_groups=top_groups),
            reply_markup=bot_stats_keyboard(stats["total_groups"]),
        )
        return ADMIN_MENU

    if data.startswith("admin_stats_groups_page_"):
        page = int(data.replace("admin_stats_groups_page_", ""))
        groups = get_all_groups()

        await query.edit_message_text(
            text=format_groups_list_text(groups, page=page, per_page=10),
            reply_markup=bot_groups_keyboard(groups, page=page, per_page=10),
        )
        return ADMIN_MENU

    if data == "admin_stats_groups":
        page = 1
        groups = get_all_groups()

        await query.edit_message_text(
            text=format_groups_list_text(groups, page=page, per_page=10),
            reply_markup=bot_groups_keyboard(groups, page=page, per_page=10),
        )
        return ADMIN_MENU

    if data.startswith("admin_stats_group_"):
        raw = data.replace("admin_stats_group_", "")

        if "_page_" in raw:
            chat_id_str, page_str = raw.split("_page_")
            chat_id = int(chat_id_str)
            page = int(page_str)
        else:
            chat_id = int(raw)
            page = 1

        group_stats = get_group_stats(chat_id)
        chat = group_stats.get("chat")
        username = chat["username"] if chat and chat["username"] else None

        await query.edit_message_text(
            text=format_group_details_text(group_stats),
            reply_markup=bot_group_details_keyboard(username=username, page=page),
            parse_mode="HTML",
            disable_web_page_preview=True,
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