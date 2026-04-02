from datetime import time
from zoneinfo import ZoneInfo
import logging

from database import get_all_user_ids, get_all_groups
from database.settings import get_setting

logger = logging.getLogger(__name__)

REMINDER_JOB_NAME = "daily_streak_reminder"
REMINDER_TZ = ZoneInfo("Asia/Tashkent")


def _get_job_queue(application):
    job_queue = getattr(application, "job_queue", None)

    if job_queue is None:
        logger.error(
            "JobQueue is not available. "
            "Make sure python-telegram-bot[job-queue] is installed."
        )
        return None

    return job_queue


def _row_get(row, key, default=None):
    try:
        return row[key]
    except Exception:
        try:
            return getattr(row, key)
        except Exception:
            return default


def _extract_group_chat_ids(group_rows):
    chat_ids = []

    for row in group_rows or []:
        chat_id = _row_get(row, "chat_id")

        if chat_id is None and isinstance(row, (tuple, list)) and row:
            chat_id = row[0]

        if chat_id is None:
            continue

        try:
            chat_ids.append(int(chat_id))
        except Exception:
            logger.warning("Skipping invalid group chat_id: %r", chat_id)

    return chat_ids


def remove_daily_reminder_job(application):
    job_queue = _get_job_queue(application)
    if job_queue is None:
        return

    jobs = job_queue.get_jobs_by_name(REMINDER_JOB_NAME)
    for job in jobs:
        job.schedule_removal()
        logger.warning("Removed old reminder job: %s", REMINDER_JOB_NAME)


async def _send_private_reminders(bot):
    sent = 0
    failed = 0

    user_ids = get_all_user_ids()

    for user_id in user_ids:
        try:
            await bot.send_message(
                chat_id=int(user_id),
                text="🔥 Daily reminder: don't lose your streak! Play today's quiz in English Lemon 🍋",
            )
            sent += 1
        except Exception:
            failed += 1
            logger.exception("Failed private reminder for user_id=%s", user_id)

    logger.warning(
        "Private reminders done: sent=%s failed=%s total=%s",
        sent,
        failed,
        len(user_ids),
    )


async def _send_group_reminders(bot):
    sent = 0
    failed = 0

    groups = get_all_groups()
    group_chat_ids = _extract_group_chat_ids(groups)

    for chat_id in group_chat_ids:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="🔥 Daily reminder: today's quiz is waiting in English Lemon 🍋\n\n/startgame to play with your group!",
            )
            sent += 1
        except Exception:
            failed += 1
            logger.exception("Failed group reminder for chat_id=%s", chat_id)

    logger.warning(
        "Group reminders done: sent=%s failed=%s total=%s",
        sent,
        failed,
        len(group_chat_ids),
    )


async def daily_streak_reminder_job(context):
    logger.warning("DAILY REMINDER JOB FIRED")

    try:
        await _send_private_reminders(context.bot)
        await _send_group_reminders(context.bot)
        logger.warning("Daily reminder job completed")
    except Exception:
        logger.exception("Daily reminder job crashed")


def schedule_daily_reminder(application):
    job_queue = _get_job_queue(application)
    if job_queue is None:
        return

    enabled = str(get_setting("streak_notify_enabled", "0")).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    hour = int(get_setting("streak_notify_hour", 20))
    minute = int(get_setting("streak_notify_minute", 0))

    remove_daily_reminder_job(application)

    if not enabled:
        logger.warning("Daily reminder is disabled; no job scheduled")
        return

    job_queue.run_daily(
        daily_streak_reminder_job,
        time=time(hour=hour, minute=minute, tzinfo=REMINDER_TZ),
        name=REMINDER_JOB_NAME,
    )

    logger.warning(
        "Scheduled daily reminder at %02d:%02d (%s)",
        hour,
        minute,
        REMINDER_TZ,
    )


async def restore_daily_reminder_jobs(application):
    logger.warning("Restoring reminder jobs from DB")
    schedule_daily_reminder(application)