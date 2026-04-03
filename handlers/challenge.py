import asyncio
import html
import logging
import re
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    User,
)
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from config import DEFAULT_QUESTIONS_PER_GAME
from services.game_service import (
    active_games,
    get_game_lock,
    create_new_game_data,
    get_existing_game_message,
    add_player_to_game,
)
from handlers.game_setup import has_active_game, get_question_count_keyboard
from database.players import get_player_by_username

logger = logging.getLogger(__name__)

# kept only so existing imports won't break
active_duels = {}

# pending challenge invites per group
active_challenges = {}

CHALLENGE_TIMEOUT_SECONDS = 60


def _display_name(user: User) -> str:
    if user.username:
        return f"@{html.escape(user.username)}"
    return html.escape(user.full_name or "Player")


def _challenge_keyboard(challenger_id: int, target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "✅ Accept Duel",
                callback_data=f"challenge_accept:{challenger_id}:{target_id}",
            ),
            InlineKeyboardButton(
                "❌ Decline",
                callback_data=f"challenge_decline:{challenger_id}:{target_id}",
            ),
        ]]
    )


def _extract_username_argument(text: str) -> Optional[str]:
    if not text:
        return None

    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None

    raw = parts[1].strip()
    if not raw:
        return None

    if raw.startswith("@"):
        raw = raw[1:]

    raw = raw.strip()
    if not raw:
        return None

    match = re.match(r"^[A-Za-z0-9_]{3,}$", raw)
    if not match:
        return None

    return raw.lower()


def _extract_text_mention_user(message) -> Optional[User]:
    if not message or not message.entities:
        return None

    for entity in message.entities:
        if entity.type == "text_mention" and getattr(entity, "user", None):
            return entity.user

    return None


async def _resolve_target_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[User]:
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return None

    # 1) Reply target
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user

    # 2) text_mention target
    text_mention_user = _extract_text_mention_user(message)
    if text_mention_user:
        return text_mention_user

    # 3) @username target
    username = _extract_username_argument(message.text or "")
    if not username:
        return None

    row = get_player_by_username(username)
    if not row:
        return None

    user_id = row["user_id"]

    try:
        member = await context.bot.get_chat_member(chat.id, user_id)
        return member.user
    except Exception:
        logger.exception(
            "Failed to resolve challenge target by username '%s' in chat %s",
            username,
            chat.id,
        )
        return None


async def _expire_challenge(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    challenger_id: int,
    target_id: int,
):
    try:
        await asyncio.sleep(CHALLENGE_TIMEOUT_SECONDS)

        challenge = active_challenges.get(chat_id)
        if not challenge:
            return

        if (
            challenge.get("challenger_id") != challenger_id
            or challenge.get("target_id") != target_id
        ):
            return

        active_challenges.pop(chat_id, None)

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=challenge["message_id"],
                text="⏳ Challenge expired.\n\nNo response from opponent.",
            )
        except Exception:
            logger.exception(
                "Failed to edit expired challenge message in chat %s",
                chat_id,
            )

    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("Challenge expiry task failed in chat %s", chat_id)


async def handle_duel_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Duel now uses the normal shared game flow.
    return


async def challenge_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()

    chat = query.message.chat
    user = query.from_user

    if chat.type == "private":
        await query.edit_message_text(
            "⚔️ Challenge works only in groups.\n\n"
            "Add English Lemon to a group and start a 1 vs 1 duel there."
        )
        return

    chat_id = chat.id

    lock = get_game_lock(chat_id)
    async with lock:
        if has_active_game(chat_id):
            existing_game = active_games.get(chat_id)
            await query.answer(
                get_existing_game_message(existing_game),
                show_alert=True,
            )
            return

        game = create_new_game_data(
            started_by=user.id,
            questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
            category="mixed",
            difficulty="mixed",
        )
        game["chat_id"] = chat_id
        game["mode"] = "duel"
        game["category"] = "mixed"
        game["difficulty"] = "mixed"
        game["min_players"] = 2
        game["max_players"] = 2
        game["setup_message_id"] = query.message.message_id
        game["join_message_id"] = None
        game["join_deadline"] = None
        game["join_seconds"] = None
        game["reminder_task"] = None
        game["reminder_message_id"] = None

        add_player_to_game(game, user)
        active_games[chat_id] = game

    await query.edit_message_text(
        "⚔️ Duel Setup\n\n"
        "Step 1 of 1 — Choose number of questions\n\n"
        "• Mode: 1 vs 1\n"
        "• Category: Mixed\n"
        "• Difficulty: Mixed",
        reply_markup=get_question_count_keyboard(back_callback="menu_main"),
    )


async def challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    challenger = update.effective_user

    if not message or not chat or not challenger:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP, "group", "supergroup"):
        await message.reply_text(
            "⚔️ Challenge works only in groups.\n\n"
            "Use /challenge in a group by replying to someone's message or using /challenge @username"
        )
        return

    target = await _resolve_target_user(update, context)
    if not target:
        await message.reply_text(
            "⚠️ To challenge someone, use one of these:\n\n"
            "• reply to their message with /challenge\n"
            "• /challenge @username\n\n"
            "Note: the username must already be known by the bot from group activity."
        )
        return

    if target.id == challenger.id:
        await message.reply_text("❌ You cannot challenge yourself.")
        return

    if target.is_bot:
        await message.reply_text("❌ You cannot challenge a bot.")
        return

    chat_id = chat.id
    lock = get_game_lock(chat_id)

    async with lock:
        if has_active_game(chat_id):
            existing_game = active_games.get(chat_id)
            await message.reply_text(get_existing_game_message(existing_game))
            return

        if chat_id in active_challenges:
            await message.reply_text(
                "⚠️ A challenge is already pending in this group.\n"
                "Please wait until it is accepted, declined, or expired."
            )
            return

        challenger_name = _display_name(challenger)
        target_name = _display_name(target)

        sent = await message.reply_text(
            (
                "⚔️ DUEL CHALLENGE 🍋\n\n"
                f"{challenger_name} has challenged {target_name}!\n\n"
                "Mode: 1 vs 1\n"
                "Category: Mixed\n"
                "Difficulty: Mixed\n"
                f"Questions: {DEFAULT_QUESTIONS_PER_GAME}\n\n"
                f"{target_name}, do you accept this duel?\n\n"
                f"⏳ Expires in {CHALLENGE_TIMEOUT_SECONDS}s"
            ),
            reply_markup=_challenge_keyboard(challenger.id, target.id),
            parse_mode="HTML",
        )

        timeout_task = asyncio.create_task(
            _expire_challenge(
                context=context,
                chat_id=chat_id,
                challenger_id=challenger.id,
                target_id=target.id,
            )
        )

        active_challenges[chat_id] = {
            "challenger_id": challenger.id,
            "target_id": target.id,
            "message_id": sent.message_id,
            "timeout_task": timeout_task,
        }


async def challenge_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return

    await query.answer()

    data = query.data or ""
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("Invalid challenge data.", show_alert=True)
        return

    action = parts[0]
    challenger_id = int(parts[1])
    target_id = int(parts[2])

    chat_id = query.message.chat.id
    actor = query.from_user

    challenge = active_challenges.get(chat_id)
    if not challenge:
        await query.answer("This challenge is no longer active.", show_alert=True)
        return

    if (
        challenge.get("challenger_id") != challenger_id
        or challenge.get("target_id") != target_id
    ):
        await query.answer("This challenge is no longer active.", show_alert=True)
        return

    if actor.id != target_id:
        await query.answer("❌ This challenge is not for you.", show_alert=True)
        return

    timeout_task = challenge.get("timeout_task")
    if timeout_task:
        timeout_task.cancel()

    if action == "challenge_decline":
        active_challenges.pop(chat_id, None)

        try:
            challenger_member = await context.bot.get_chat_member(chat_id, challenger_id)
            challenger_user = challenger_member.user
            challenger_name = _display_name(challenger_user)
        except Exception:
            logger.exception("Failed to fetch challenger info for decline")
            challenger_name = "the challenger"

        await query.edit_message_text(
            (
                "❌ Duel declined.\n\n"
                f"{_display_name(actor)} declined the challenge from {challenger_name}."
            ),
            parse_mode="HTML",
        )
        return

    lock = get_game_lock(chat_id)
    async with lock:
        if has_active_game(chat_id):
            active_challenges.pop(chat_id, None)
            existing_game = active_games.get(chat_id)
            await query.answer(
                get_existing_game_message(existing_game),
                show_alert=True,
            )
            try:
                await query.edit_message_text(
                    "⚠️ This challenge can no longer start because another game is active."
                )
            except Exception:
                logger.exception(
                    "Failed to edit challenge message after active game conflict"
                )
            return

        try:
            challenger_member = await context.bot.get_chat_member(chat_id, challenger_id)
            challenger_user = challenger_member.user
        except Exception:
            logger.exception("Failed to fetch challenger info for duel accept")
            active_challenges.pop(chat_id, None)
            await query.edit_message_text(
                "❌ Could not load challenger information. Please send /challenge again."
            )
            return

        game = create_new_game_data(
            started_by=challenger_id,
            questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
            category="mixed",
            difficulty="mixed",
        )
        game["chat_id"] = chat_id
        game["mode"] = "duel"
        game["category"] = "mixed"
        game["difficulty"] = "mixed"
        game["min_players"] = 2
        game["max_players"] = 2
        game["setup_message_id"] = query.message.message_id
        game["join_message_id"] = None
        game["join_deadline"] = None
        game["join_seconds"] = None
        game["reminder_task"] = None
        game["reminder_message_id"] = None
        game["challenge_target_id"] = target_id

        add_player_to_game(game, challenger_user)
        add_player_to_game(game, actor)

        active_games[chat_id] = game
        active_challenges.pop(chat_id, None)

    await query.edit_message_text(
        (
            "⚔️ Duel accepted! 🍋\n\n"
            f"{_display_name(challenger_user)} ✅\n"
            f"{_display_name(actor)} ✅\n\n"
            "⚡ Get ready..."
        ),
        parse_mode="HTML",
    )

    for i in [3, 2, 1]:
        await asyncio.sleep(1)
        try:
            await context.bot.send_message(chat_id, f"{i}...")
        except Exception:
            logger.exception("Failed to send duel countdown in chat %s", chat_id)

    await asyncio.sleep(0.5)

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "⚔️ Duel Setup\n\n"
            "Step 1 of 1 — Choose number of questions\n\n"
            "• Mode: 1 vs 1\n"
            "• Category: Mixed\n"
            "• Difficulty: Mixed"
        ),
        reply_markup=get_question_count_keyboard(back_callback="menu_main"),
    )