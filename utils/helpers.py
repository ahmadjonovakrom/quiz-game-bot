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
    total = len(game.get("players", {}))
    questions = game.get("questions_per_game", 10)
    category = game.get("category", "mixed")

    category_map = {
        "mixed": "Mixed",
        "vocabulary": "Vocabulary",
        "grammar": "Grammar",
        "idioms_phrases": "Idioms & Phrases",
        "synonyms": "Synonyms",
        "collocations": "Collocations",
    }

    category_name = category_map.get(
        str(category).lower(),
        str(category).replace("_", " ").title()
    )

    if remaining <= 10:
        if blink:
            timer_text = (
                f"🚨 <b>LAST {remaining} SECONDS!</b>\n"
                f"🔥 <b>JOIN NOW</b>"
            )
        else:
            timer_text = (
                f"⚠️ <b>LAST {remaining} SECONDS!</b>\n"
                f"⏳ <b>HURRY UP</b>"
            )
    else:
        timer_text = f"⏳ Registration is open <b>({remaining}s)</b>"

    return (
        "🎮 <b>English Lemon Quiz</b>\n\n"
        f"{timer_text}\n\n"
        f"👥 Total: <b>{total}</b>\n"
        f"❓ Questions: <b>{questions}</b>\n"
        f"📚 Category: <b>{category_name}</b>\n"
        f"✅ Minimum needed: <b>{MIN_PLAYERS}</b>"
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