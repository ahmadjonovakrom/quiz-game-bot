import asyncio
import html
import logging

from telegram.constants import ChatMemberStatus

from config import ADMIN_ID, MIN_PLAYERS

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def is_group_admin(context, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        logger.exception(
            "Failed to check admin status for user %s in chat %s",
            user_id,
            chat_id,
        )
        return False


async def is_game_controller(context, chat_id: int, user_id: int, game: dict) -> bool:
    if not game:
        return False

    starter_id = game.get("started_by") or game.get("started_by_user_id")

    return (
        user_id == starter_id
        or is_admin(user_id)
        or await is_group_admin(context, chat_id, user_id)
    )


async def is_running_game_controller(context, chat_id: int, user_id: int) -> bool:
    return is_admin(user_id) or await is_group_admin(context, chat_id, user_id)


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
    min_players = game.get("min_players", MIN_PLAYERS)

    if remaining <= 10:
        if blink:
            timer_line = f"🚨 Registration is open ({remaining}s)"
        else:
            timer_line = f"⚠️ Registration is open ({remaining}s)"
    else:
        timer_line = f"Registration is open ({remaining}s)"

    joined_names = []
    for user_id, player in players.items():
        if isinstance(player, dict):
            name = player.get("full_name") or player.get("username") or "Player"
        else:
            name = getattr(player, "full_name", None) or getattr(player, "username", None) or "Player"

        safe_name = html.escape(str(name))
        mention = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
        joined_names.append(mention)

    joined_text = ", ".join(joined_names) if joined_names else "-"

    if total >= min_players:
        min_needed_text = f"{min_players} ✅"
    else:
        min_needed_text = str(min_players)

    return "\n".join([
        timer_line,
        "",
        "Joined:",
        joined_text,
        "",
        f"Total: {total}",
        f"Minimum needed: {min_needed_text}",
    ])


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