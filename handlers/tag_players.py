import asyncio
import html
import logging
import random
import time

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from database import pick_random_group_tag_candidates
from services.game_service import active_games

logger = logging.getLogger(__name__)

CALL_COOLDOWN = 60
MAX_PLAYERS = 10
CANDIDATE_LIMIT = 100
RECENT_TAG_COOLDOWN = 600  # 10 minutes

_last_call = {}
_recent_called = {}


def is_joining(chat_id: int) -> bool:
    game = active_games.get(chat_id)
    return bool(game and game.get("status") == "joining")


def can_call(chat_id: int):
    now = time.time()
    last = _last_call.get(chat_id, 0)

    if now - last < CALL_COOLDOWN:
        return False, int(CALL_COOLDOWN - (now - last))

    _last_call[chat_id] = now
    return True, 0


def was_recently_called(chat_id: int, user_id: int) -> bool:
    chat_map = _recent_called.get(chat_id, {})
    last = chat_map.get(user_id, 0)
    return time.time() - last < RECENT_TAG_COOLDOWN


def mark_called(chat_id: int, user_ids: list[int]) -> None:
    chat_map = _recent_called.setdefault(chat_id, {})
    now = time.time()
    for uid in user_ids:
        chat_map[uid] = now


async def is_member(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.RESTRICTED,
        )
    except Exception:
        logger.exception(
            "Failed to check member status for user %s in chat %s",
            user_id,
            chat_id,
        )
        return False


def build_mention(row) -> str:
    username = (row["username"] or "").strip()
    full_name = html.escape(
        (row["full_name"] or "").strip() or username or f"User {row['user_id']}"
    )

    if username:
        return f"@{username}"

    return f'<a href="tg://user?id={row["user_id"]}">{full_name}</a>'


def build_message(mentions: list[str]) -> str:
    first = ", ".join(mentions[:5])
    second = ", ".join(mentions[5:10])

    quote_lines = []
    if first:
        quote_lines.append(first)
    if second:
        quote_lines.append(second)

    quote_text = "\n".join(quote_lines)

    return (
        "🟡 Players called!\n\n"
        f"<blockquote expandable>{quote_text}</blockquote>\n\n"
        "🎮 Join now!"
    )


async def delete_message_safely(msg, log_text: str):
    if not msg:
        return

    try:
        await msg.delete()
    except Exception:
        logger.exception(log_text)


async def send_temp_reply(message, text: str, seconds: int = 3):
    sent = await message.reply_text(text)

    await delete_message_safely(
        message,
        "Failed to delete /callplayers command message",
    )

    await asyncio.sleep(seconds)

    await delete_message_safely(
        sent,
        "Failed to delete temporary /callplayers reply",
    )


async def callplayers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    caller = update.effective_user

    if not message or not chat or not caller or chat.type not in ("group", "supergroup"):
        return

    if not is_joining(chat.id):
        await send_temp_reply(message, "No active game to join.", 3)
        return

    ok, wait = can_call(chat.id)
    if not ok:
        await send_temp_reply(message, f"Wait {wait}s before calling again.", 3)
        return

    candidates = list(pick_random_group_tag_candidates(chat.id, limit=CANDIDATE_LIMIT))

    if not candidates:
        await send_temp_reply(
            message,
            "No players found.\n\nAsk people to send a message in the group first, then try again.",
            4,
        )
        return

    random.shuffle(candidates)

    valid = []
    seen = set()

    game = active_games.get(chat.id) or {}
    joined_ids = set((game.get("players") or {}).keys())

    # First pass: avoid recently called users
    for row in candidates:
        uid = row["user_id"]

        if uid == caller.id:
            continue
        if uid in joined_ids:
            continue
        if uid in seen:
            continue
        if was_recently_called(chat.id, uid):
            continue

        if await is_member(context, chat.id, uid):
            valid.append(row)
            seen.add(uid)

        if len(valid) >= MAX_PLAYERS:
            break

    # Second pass: allow recently called users too if needed
    if not valid:
        for row in candidates:
            uid = row["user_id"]

            if uid == caller.id:
                continue
            if uid in joined_ids:
                continue
            if uid in seen:
                continue

            if await is_member(context, chat.id, uid):
                valid.append(row)
                seen.add(uid)

            if len(valid) >= MAX_PLAYERS:
                break

    if not valid:
        await send_temp_reply(message, "No current members to tag.", 3)
        return

    picked = valid[:MAX_PLAYERS]
    mark_called(chat.id, [row["user_id"] for row in picked])

    mentions = [build_mention(row) for row in picked]
    text = build_message(mentions)

    await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    await delete_message_safely(
        message,
        "Failed to delete /callplayers command message",
    )