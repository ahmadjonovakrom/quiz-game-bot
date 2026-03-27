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
CANDIDATE_LIMIT = 30

_last_call = {}


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


async def is_member(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
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
        (row["full_name"] or "").strip() or f"User {row['user_id']}"
    )

    if username:
        if not username.startswith("@"):
            username = f"@{username}"
        return html.escape(username)

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


async def callplayers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat or chat.type not in ("group", "supergroup"):
        return

    if not is_joining(chat.id):
        await message.reply_text("No active game to join.")
        return

    ok, wait = can_call(chat.id)
    if not ok:
        await message.reply_text(f"Wait {wait}s before calling again.")
        return

    candidates = pick_random_group_tag_candidates(chat.id, limit=CANDIDATE_LIMIT)

    if not candidates:
        await message.reply_text("No players found.")
        return

    valid = []
    seen = set()

    caller_id = update.effective_user.id

    for row in candidates:
        uid = row["user_id"]

        if uid == caller_id:
            continue

        if uid in seen:
            continue

        if await is_member(context, chat.id, uid):
            valid.append(row)
            seen.add(uid)

        if len(valid) >= MAX_PLAYERS:
            break

    if not valid:
        await message.reply_text("No current members to tag.")
        return

    random.shuffle(valid)
    mentions = [build_mention(row) for row in valid[:MAX_PLAYERS]]
    text = build_message(mentions)

    # 1️⃣ Send main message (not as reply)
    await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    # 2️⃣ Delete /callplayers command message
    try:
        await message.delete()
    except:
        pass