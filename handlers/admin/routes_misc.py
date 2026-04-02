from telegram.ext import ConversationHandler

from utils.keyboards import (
    admin_danger_keyboard,
    admin_reset_confirm_keyboard,
    admin_settings_keyboard,
    settings_value_keyboard,
    settings_daily_reminder_keyboard,
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
        reminder_hour = int(settings.get("streak_notify_hour", 20))
        reminder_minute = int(settings.get("streak_notify_minute", 0))

        reminder_text = (
            f"ON ({reminder_hour:02d}:{reminder_minute:02d})"
            if reminder_enabled
            else "OFF"
        )

        text = (
            "⚙️ Settings\n\n"
            f"👥 Min Players: {settings.get('min_players', 2)}\n"
            f"⏱ Join Time: {settings.get('join_seconds', 90)}s\n"
            f"⏱ Question Time: {settings.get('question_seconds', 18)}s\n"
            f"⚡ Speed Bonus: +{settings.get('speed_bonus_points', 5)} 🍋 "
            f"(first {settings.get('speed_bonus_seconds', 5)}s)\n\n"
            f"🍋 Easy Points: {settings.get('points_easy', 15)}\n"
            f"🍋 Medium Points: {settings.get('points_medium', 25)}\n"
            f"🍋 Hard Points: {settings.get('points_hard', 35)}\n\n"
            f"🔥 Daily Reminder: {reminder_text}"
        )

        await query.edit_message_text(
            text,
            reply_markup=admin_settings_keyboard(settings),
        )
        return ADMIN_MENU

    if data == "settings_daily_reminder":
        from database import get_all_settings

        settings = get_all_settings()
        enabled = bool(settings.get("streak_notify_enabled", 0))
        hour = int(settings.get("streak_notify_hour", 20))
        minute = int(settings.get("streak_notify_minute", 0))

        await query.edit_message_text(
            "🔥 Daily Reminder\n\n"
            f"Current status: {'ON' if enabled else 'OFF'}\n"
            f"Current time: {hour:02d}:{minute:02d}\n\n"
            "Choose an option below or type a custom time.",
            reply_markup=settings_daily_reminder_keyboard(settings),
        )
        context.user_data["setting_key"] = "daily_reminder"
        return ADMIN_MENU

    if data.startswith("settings_daily_toggle:"):
        from database import set_setting

        action = data.split(":", 1)[1]
        set_setting("streak_notify_enabled", 1 if action == "on" else 0)

        context.user_data.clear()

        return await _show_settings_again(query, context)

    if data.startswith("settings_daily_time:"):
        from database import set_setting

        time_str = data.split(":", 1)[1]
        hour_str, minute_str = time_str.split(":")

        set_setting("streak_notify_hour", int(hour_str))
        set_setting("streak_notify_minute", int(minute_str))
        set_setting("streak_notify_enabled", 1)

        context.user_data.clear()

        return await _show_settings_again(query, context)

    if data == "settings_daily_custom":
        context.user_data["setting_key"] = "daily_reminder"
        await query.edit_message_text(
            "🔥 Daily Reminder\n\n"
            "Send:\n"
            "• on\n"
            "• off\n"
            "• or custom time like 20:00",
            reply_markup=nav_keyboard("admin_settings"),
        )
        return SETTING_VALUE

    if data.startswith("settings_value:"):
        from database import set_setting

        _, key, value = data.split(":", 2)
        set_setting(key, int(value))
        context.user_data.clear()
        return await _show_settings_again(query, context)

    if data.startswith("settings_custom:"):
        key = data.split(":", 1)[1]
        context.user_data["setting_key"] = key

        labels = {
            "min_players": "👥 Min Players",
            "join_seconds": "⏱ Join Time",
            "question_seconds": "⏱ Question Time",
            "speed_bonus_seconds": "⚡ Speed Bonus Time",
            "points_easy": "🍋 Easy Points",
            "points_medium": "🍋 Medium Points",
            "points_hard": "🍋 Hard Points",
        }

        label = labels.get(key, key)
        await query.edit_message_text(
            f"✏️ Update Setting\n\nSend custom value for:\n{label}",
            reply_markup=nav_keyboard("admin_settings"),
        )
        return SETTING_VALUE

    if data.startswith("settings_"):
        from database import get_all_settings

        key = data.replace("settings_", "")
        if key in {
            "min_players",
            "join_seconds",
            "question_seconds",
            "speed_bonus_seconds",
            "points_easy",
            "points_medium",
            "points_hard",
        }:
            labels = {
                "min_players": "👥 Min Players",
                "join_seconds": "⏱ Join Time",
                "question_seconds": "⏱ Question Time",
                "speed_bonus_seconds": "⚡ Speed Bonus Time",
                "points_easy": "🍋 Easy Points",
                "points_medium": "🍋 Medium Points",
                "points_hard": "🍋 Hard Points",
            }
            label = labels.get(key, key)

            settings = get_all_settings()
            current_value = settings.get(key)

            await query.edit_message_text(
                f"{label}\n\nChoose a value or type your own.",
                reply_markup=settings_value_keyboard(key, current_value),
            )
            return ADMIN_MENU

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


async def _show_settings_again(query, context):
    from database import get_all_settings

    settings = get_all_settings()

    reminder_enabled = bool(settings.get("streak_notify_enabled", 0))
    reminder_hour = int(settings.get("streak_notify_hour", 20))
    reminder_minute = int(settings.get("streak_notify_minute", 0))

    reminder_text = (
        f"ON ({reminder_hour:02d}:{reminder_minute:02d})"
        if reminder_enabled
        else "OFF"
    )

    text = (
        "⚙️ Settings\n\n"
        f"👥 Min Players: {settings.get('min_players', 2)}\n"
        f"⏱ Join Time: {settings.get('join_seconds', 90)}s\n"
        f"⏱ Question Time: {settings.get('question_seconds', 18)}s\n"
        f"⚡ Speed Bonus: +{settings.get('speed_bonus_points', 5)} 🍋 "
        f"(first {settings.get('speed_bonus_seconds', 5)}s)\n\n"
        f"🍋 Easy Points: {settings.get('points_easy', 15)}\n"
        f"🍋 Medium Points: {settings.get('points_medium', 25)}\n"
        f"🍋 Hard Points: {settings.get('points_hard', 35)}\n\n"
        f"🔥 Daily Reminder: {reminder_text}"
    )

    await query.edit_message_text(
        text,
        reply_markup=admin_settings_keyboard(settings),
    )
    return ADMIN_MENU