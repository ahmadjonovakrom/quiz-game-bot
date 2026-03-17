import asyncio
import html
import logging
from config import ADMIN_ID, MIN_PLAYERS

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def safe_task(coro):
    async def wrapper():
        try:
            await coro
        except Exception:
            logger.exception("Background task crashed")

    task = asyncio.create_task(wrapper())
    return task


def build_join_text(game, remaining):
    if not game["players"]:
        return f"Registration is open ({remaining}s)"

    players_text = ", ".join(game["players"].values())

    return (
        f"Registration is open ({remaining}s)\n\n"
        f"Joined:\n{players_text}\n\n"
        f"Total: {len(game['players'])}\n"
        f"Minimum needed: {MIN_PLAYERS}"
    )


async def safe_delete_message(bot, chat_id, message_id):
    if not message_id:
        return

    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(
            "Could not delete message %s in chat %s: %s",
            message_id,
            chat_id,
            e,
        )


def clickable_name(user):
    safe_name = html.escape(user.full_name or user.first_name or "Player")
    return f'<a href="tg://user?id={user.id}">{safe_name}</a>'