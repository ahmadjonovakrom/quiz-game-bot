from telegram.ext import ConversationHandler

from utils.keyboards import (
    admin_danger_keyboard,
    admin_reset_confirm_keyboard,
    admin_settings_keyboard,
)
from utils.texts import format_bot_stats_text

from services.stats_service import get_bot_stats_service

from .questions import nav_keyboard
from .states import *


async def handle_misc_routes(
    query,
    context,
    update,
    show_admin_panel_message,
    show_questions_menu,
    reset_stats,
):
    data = query.data

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

    if data == "admin_page_info":
        await query.answer()
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

    return None