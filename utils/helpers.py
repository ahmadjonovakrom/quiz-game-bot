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

    return asyncio.create_task(wrapper())


def format_category_name(category: str) -> str:
    mapping = {
        "mixed": "Mixed",
        "vocabulary": "Vocabulary",
        "grammar": "Grammar",
        "idioms": "Idioms",
        "synonyms": "Synonyms",
    }
    return mapping.get(category, category.capitalize())


def build_join_text(game, remaining: int) -> str:
    players = game.get("players", {})

    if not players:
        return (
            f"Registration is open ({remaining}s)\n\n"
            f"Total: 0\n"
            f"Minimum needed: {MIN_PLAYERS}"
        )

    players_text = ", ".join(players.values())

    return (
        f"Registration is open ({remaining}s)\n\n"
        f"Joined:\n{players_text}\n\n"
        f"Total: {len(players)}\n"
        f"Minimum needed: {MIN_PLAYERS}"
    )


async def safe_delete_message(bot, chat_id, message_id):
    if not message_id:
        return

    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


def clickable_name(user) -> str:
    safe_name = html.escape(user.full_name or user.first_name or "Player")
    return f'<a href="tg://user?id={user.id}">{safe_name}</a>'