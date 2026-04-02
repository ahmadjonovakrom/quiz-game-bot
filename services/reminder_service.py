from datetime import time
from zoneinfo import ZoneInfo
import logging

from config import ADMIN_ID
from database.settings import get_setting

logger = logging.getLogger(__name__)

REMINDER_JOB_NAME = "daily_streak_reminder"
REMINDER_TZ = ZoneInfo("Asia/Tashkent")


def _get_job_queue(application):
    job_queue = getattr(application, "job_queue", None)

    if job_queue is None:
        logger.error(
            "JobQueue is not available. "
            "Make sure APScheduler / python-telegram-bot[job-queue] is installed."
        )
        return None

    return job_queue


def remove_daily_reminder_job(application):
    job_queue = _get_job_queue(application)
    if job_queue is None:
        return

    jobs = job_queue.get_jobs_by_name(REMINDER_JOB_NAME)
    for job in jobs:
        job.schedule_removal()
        logger.warning("Removed old reminder job: %s", REMINDER_JOB_NAME)


async def daily_streak_reminder_job(context):
    logger.warning("DAILY REMINDER JOB FIRED")

    chat_id = int(get_setting("streak_notify_chat_id", ADMIN_ID) or ADMIN_ID)

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔥 Daily reminder: don't lose your streak! Play today's quiz in English Lemon 🍋",
        )
        logger.warning("Reminder sent successfully to chat_id=%s", chat_id)
    except Exception:
        logger.exception("Failed to send daily reminder to chat_id=%s", chat_id)


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