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
    needed = max(0, min_players - total)

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

    if needed == 0:
        need_line = "✅ Enough players joined"
    elif needed == 1:
        need_line = "Need 1 more player to start"
    else:
        need_line = f"Need {needed} more players to start"

    postpone_count = int(game.get("postpone_count", 0))
    max_postpones = int(game.get("max_postpones", 0))

    if max_postpones > 0:
        extensions_left = max(0, max_postpones - postpone_count)
        extension_line = f"Extensions left: {extensions_left}"
    else:
        extension_line = None

    parts = [
        timer_line,
        "",
        f"Players: {total}/{min_players}",
        need_line,
        "",
        "Joined:",
        joined_text,
    ]

    if extension_line:
        parts.extend(["", extension_line])

    return "\n".join(parts)


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