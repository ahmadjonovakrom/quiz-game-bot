from telegram.ext import ConversationHandler

from utils.keyboards import (
    admin_danger_keyboard,
    admin_reset_confirm_keyboard,
    admin_settings_keyboard,
)

from .questions import nav_keyboard
from .states import *


async def handle_misc_routes(
    query,
    context,
    update,
    show_admin_panel_message,
    show_questions_menu,
    reset_all_time_leaderboard,
    full_reset_all_data,
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
        return None

    if data == "admin_settings":
        from database import get_all_settings

        settings = get_all_settings()

        reminder_enabled = bool(settings.get("streak_notify_enabled", 0))
        reminder_hour = settings.get("streak_notify_hour", 20)
        reminder_minute = settings.get("streak_notify_minute", 0)

        reminder_text = (
            f"ON ({int(reminder_hour):02d}:{int(reminder_minute):02d})"
            if reminder_enabled
            else "OFF"
        )

        text = (
            "⚙️ Settings\n\n"
            f"👥 Min Players: {settings.get('min_players', 2)}\n"
            f"⏱ Join Time: {settings.get('join_seconds', 90)}s\n"
            f"⏱ Question Time: {settings.get('question_seconds', 18)}s\n"
            f"⚡ Speed Bonus Time: {settings.get('speed_bonus_seconds', 5)}s\n\n"
            f"🍋 Easy Points: {settings.get('points_easy', 15)}\n"
            f"🍋 Medium Points: {settings.get('points_medium', 25)}\n"
            f"🍋 Hard Points: {settings.get('points_hard', 35)}\n\n"
            f"🔥 Daily Reminder: {reminder_text}"
        )

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

    if data == "admin_reset_all_time_confirm":
        await query.edit_message_text(
            "⚠️ Reset ALL-TIME leaderboard stats?\n\n"
            "This will reset player and group all-time stats.\n"
            "It will NOT affect daily, weekly, or monthly rankings.\n\n"
            "This cannot be undone.",
            reply_markup=admin_reset_confirm_keyboard("admin_reset_all_time_yes"),
        )
        return ADMIN_MENU

    if data == "admin_full_reset_confirm":
        await query.edit_message_text(
            "💥 FULL RESET (ALL DATA)\n\n"
            "This will clear gameplay data, leaderboard data, game history, "
            "and daily/weekly/monthly history.\n\n"
            "Questions and settings will be kept.\n\n"
            "This cannot be undone.",
            reply_markup=admin_reset_confirm_keyboard("admin_full_reset_yes"),
        )
        return ADMIN_MENU

    if data == "admin_reset_all_time_yes":
        await reset_all_time_leaderboard(update, context)
        return ADMIN_MENU

    if data == "admin_full_reset_yes":
        await full_reset_all_data(update, context)
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