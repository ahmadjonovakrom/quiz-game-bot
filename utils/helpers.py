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
        "idioms_phrases": "Idioms & Phrases",
        "synonyms": "Synonyms",
        "collocations": "Collocations",
    }
    return mapping.get(str(category).lower(), str(category).replace("_", " ").title())


def build_join_text(game, remaining: int, blink: bool = False) -> str:
    players = game.get("players", {})
    total = len(players)

    if remaining <= 10:
        if blink:
            timer_line = f"🚨 Registration is open ({remaining}s)"
        else:
            timer_line = f"⚠️ Registration is open ({remaining}s)"
    else:
        timer_line = f"Registration is open ({remaining}s)"

    joined_names = []
    for player in players.values():
        if isinstance(player, dict):
            name = player.get("full_name") or player.get("username") or "Player"
        else:
            name = getattr(player, "full_name", None) or getattr(player, "username", None) or "Player"

        joined_names.append(html.escape(str(name)))

    joined_text = "\n".join(joined_names) if joined_names else "-"

    return (
        f"{timer_line}\n\n"
        f"Joined:\n"
        f"{joined_text}\n\n"
        f"Total: {total}\n"
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