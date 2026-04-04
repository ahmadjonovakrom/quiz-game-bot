"""
handlers/duel.py

Telegram handler layer for duels.  This is intentionally thin:
- validates Telegram context (chat type, user identity)
- calls duel_service for all business logic
- handles all Telegram I/O (send/edit messages)
- never touches duel_registry directly

Replaces: handlers/challenge.py

bot.py wiring (replace old challenge handlers with these):
    app.add_handler(CommandHandler("challenge", duel_challenge_command))
    app.add_handler(CallbackQueryHandler(
        duel_callback_handler,
        pattern=r"^duel:",
    ))
"""

from __future__ import annotations

import asyncio
import html
import logging
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    User,
)
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from config import DEFAULT_QUESTIONS_PER_GAME
from database.players import get_player_by_username
from services.duel_state import (
    DuelPhase,
    DuelState,
    DuelAlreadyActive,
    InvalidTransition,
    NotAParticipant,
    AlreadyJoined,
    BadToken,
    duel_registry,
)
from services.duel_service import (
    CHALLENGE_TIMEOUT_SECONDS,
    DUEL_JOIN_SECONDS,
    DUEL_COUNTDOWN_SECONDS,
    create_challenge,
    record_challenge_message,
    decline_challenge,
    accept_challenge,
    configure_duel,
    open_duel_lobby,
    player_join,
    finish_duel,
    cancel_duel,
    create_rematch,
    make_duel_player,
)
from utils.helpers import safe_delete_message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Callback data format:  "duel:<action>:<token>[:<extra>]"
#
# token is the per-challenge HMAC tag from duel_registry.make_callback_token().
# This replaces raw user IDs in callback_data, eliminating spoofing.
# ---------------------------------------------------------------------------

_PREFIX = "duel"


def _cb(action: str, token: str, extra: str = "") -> str:
    parts = [_PREFIX, action, token]
    if extra:
        parts.append(extra)
    return ":".join(parts)


def _parse_cb(data: str):
    """Returns (action, token, extra_or_None) or raises ValueError."""
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != _PREFIX:
        raise ValueError(f"Not a duel callback: {data!r}")
    action = parts[1]
    token  = parts[2]
    extra  = parts[3] if len(parts) > 3 else None
    return action, token, extra


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------


def _challenge_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ Accept",
            callback_data=_cb("accept", token),
        ),
        InlineKeyboardButton(
            "❌ Decline",
            callback_data=_cb("decline", token),
        ),
    ]])


def _join_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "⚔️ Join Duel",
            callback_data=_cb("join", token),
        ),
    ]])


def _setup_keyboard(token: str) -> InlineKeyboardMarkup:
    """Question count picker for duel setup."""
    counts = [5, 10, 15, 20]
    rows = []
    row = []
    for count in counts:
        row.append(InlineKeyboardButton(
            str(count),
            callback_data=_cb("setup_q", token, str(count)),
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(
        "❌ Cancel",
        callback_data=_cb("cancel_setup", token),
    )])
    return InlineKeyboardMarkup(rows)


def _results_keyboard(token: str, db_game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🔁 Rematch",
            callback_data=_cb("rematch", token, str(db_game_id)),
        ),
    ]])


# ---------------------------------------------------------------------------
# Text builders
# ---------------------------------------------------------------------------


def _safe(text: str) -> str:
    return html.escape(str(text))


def _challenge_text(state: DuelState) -> str:
    c = state.challenger.display_name()
    t = state.target.display_name()
    return (
        f"⚔️ <b>DUEL CHALLENGE</b>\n\n"
        f"{_safe(c)} has challenged {_safe(t)}!\n\n"
        f"• Category: Mixed\n"
        f"• Difficulty: Mixed\n\n"
        f"{_safe(t)}, do you accept?\n\n"
        f"⏳ Expires in {CHALLENGE_TIMEOUT_SECONDS}s"
    )


def _setup_text(state: DuelState) -> str:
    c = state.challenger.display_name()
    t = state.target.display_name()
    return (
        f"⚔️ <b>DUEL SETUP</b>\n\n"
        f"{_safe(c)} vs {_safe(t)}\n\n"
        f"Choose number of questions:"
    )


def _join_text(state: DuelState) -> str:
    c = state.challenger.display_name()
    t = state.target.display_name()
    remaining = state.join_remaining_seconds()

    joined_lines = []
    for player in state.both_players:
        mark = "✅" if state.has_joined(player.user_id) else "⏳"
        joined_lines.append(f"{mark} {_safe(player.display_name())}")

    return (
        f"⚔️ <b>DUEL LOBBY</b>\n\n"
        f"{_safe(c)} vs {_safe(t)}\n\n"
        + "\n".join(joined_lines)
        + f"\n\n⏳ {remaining}s to join"
    )


# ---------------------------------------------------------------------------
# /challenge command
# ---------------------------------------------------------------------------


async def duel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    caller  = update.effective_user

    if not message or not chat or not caller:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.reply_text(
            "⚔️ Challenges only work in groups."
        )
        return

    target = await _resolve_target(update, context)
    if target is None:
        await message.reply_text(
            "⚠️ Mention someone to challenge:\n"
            "• Reply to their message with /challenge\n"
            "• /challenge @username"
        )
        return

    # Also block if an existing quiz game (non-duel) is running.
    # Import here to avoid circular imports with existing game_service.
    from services.game_service import active_games
    existing = active_games.get(chat.id)
    if existing and existing.get("status") in ("setup", "joining", "running"):
        await message.reply_text(
            "A quiz game is already in progress. Finish it first."
        )
        return

    try:
        state = await create_challenge(
            chat_id=chat.id,
            challenger_user=caller,
            target_user=target,
        )
    except DuelAlreadyActive:
        await message.reply_text(
            "A duel is already pending or running in this group."
        )
        return
    except ValueError as exc:
        await message.reply_text(f"❌ {exc}")
        return

    token = duel_registry.make_callback_token(state)

    sent = await message.reply_text(
        _challenge_text(state),
        reply_markup=_challenge_keyboard(token),
        parse_mode="HTML",
    )

    # Store message_id AFTER sending (network call outside lock is safe here
    # because state already exists; we're just annotating it).
    await record_challenge_message(chat.id, sent.message_id)

    # Schedule a task to edit the message when the challenge expires.
    asyncio.create_task(
        _edit_on_expiry(
            context=context,
            chat_id=chat.id,
            message_id=sent.message_id,
            token=state.token,       # raw token, not HMAC tag
        )
    )


async def _edit_on_expiry(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    token: str,                      # raw DuelState.token
) -> None:
    """
    Wait, then edit the challenge message to 'expired' if it hasn't been
    acted upon.  Uses raw token (not HMAC) to identify the specific state.
    """
    await asyncio.sleep(CHALLENGE_TIMEOUT_SECONDS + 2)

    state = duel_registry.get_state(chat_id)
    # If state is gone or token changed, challenge was already handled.
    if state is not None and state.token == token:
        # Still pending — shouldn't happen (registry expires it), but guard.
        return

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⏳ Challenge expired. No response from opponent.",
        )
    except Exception:
        pass   # Message may already be edited by accept/decline flow.


# ---------------------------------------------------------------------------
# Unified callback handler
# ---------------------------------------------------------------------------


async def duel_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if not query or not query.from_user or not query.message:
        return

    await query.answer()

    try:
        action, token, extra = _parse_cb(query.data)
    except ValueError:
        logger.warning("Unparseable duel callback: %r", query.data)
        return

    chat_id = query.message.chat_id
    actor   = query.from_user

    # Dispatch
    dispatch = {
        "accept":       _handle_accept,
        "decline":      _handle_decline,
        "setup_q":      _handle_setup_q,
        "cancel_setup": _handle_cancel_setup,
        "join":         _handle_join,
        "rematch":      _handle_rematch,
    }

    handler = dispatch.get(action)
    if handler is None:
        logger.warning("Unknown duel action: %r", action)
        return

    try:
        await handler(
            query=query,
            context=context,
            chat_id=chat_id,
            actor=actor,
            token=token,
            extra=extra,
        )
    except BadToken:
        await query.answer("This button is no longer valid.", show_alert=True)
    except NotAParticipant:
        await query.answer("This duel is not for you.", show_alert=True)
    except AlreadyJoined:
        await query.answer("You already joined.", show_alert=True)
    except InvalidTransition as exc:
        logger.warning("InvalidTransition in duel callback: %s", exc)
        await query.answer("This action is no longer available.", show_alert=True)
    except DuelAlreadyActive:
        await query.answer("A duel is already in progress.", show_alert=True)
    except Exception:
        logger.exception("Unhandled error in duel_callback_handler")
        await query.answer("Something went wrong. Please try again.", show_alert=True)


# ---------------------------------------------------------------------------
# Individual action handlers
# ---------------------------------------------------------------------------


async def _handle_accept(query, context, chat_id, actor, token, extra):
    state = duel_registry.get_state(chat_id)
    if state is None:
        await query.edit_message_text("⏳ This challenge has already expired.")
        return

    state = await accept_challenge(
        chat_id=chat_id,
        actor_id=actor.id,
        token=token,
    )

    # Transition to setup: challenger picks question count.
    new_token = duel_registry.make_callback_token(state)

    await query.edit_message_text(
        _setup_text(state),
        reply_markup=_setup_keyboard(new_token),
        parse_mode="HTML",
    )

    await configure_duel(
        chat_id=chat_id,
        questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
        setup_message_id=query.message.message_id,
    )


async def _handle_decline(query, context, chat_id, actor, token, extra):
    state = duel_registry.get_state(chat_id)
    if state is None:
        await query.edit_message_text("This challenge is no longer active.")
        return

    challenger_name = state.challenger.display_name()
    actor_name = make_duel_player(actor).display_name()

    await decline_challenge(
        chat_id=chat_id,
        actor_id=actor.id,
        token=token,
    )

    await query.edit_message_text(
        f"❌ {_safe(actor_name)} declined the duel challenge from {_safe(challenger_name)}.",
        parse_mode="HTML",
    )


async def _handle_setup_q(query, context, chat_id, actor, token, extra):
    """Challenger selects question count, then we open the join lobby."""
    state = duel_registry.get_state(chat_id)
    if state is None:
        await query.edit_message_text("Duel setup expired.")
        return

    # Any participant can confirm setup.
    if not state.is_participant(actor.id):
        raise NotAParticipant()

    try:
        q_count = int(extra)
        assert q_count in (5, 10, 15, 20)
    except (TypeError, ValueError, AssertionError):
        await query.answer("Invalid question count.", show_alert=True)
        return

    await configure_duel(
        chat_id=chat_id,
        questions_per_game=q_count,
        setup_message_id=query.message.message_id,
    )

    # Open the join lobby.
    state = await open_duel_lobby(
        chat_id=chat_id,
        join_message_id=query.message.message_id,
        join_seconds=DUEL_JOIN_SECONDS,
    )

    new_token = duel_registry.make_callback_token(state)

    await query.edit_message_text(
        _join_text(state),
        reply_markup=_join_keyboard(new_token),
        parse_mode="HTML",
    )

    # Start a background task that refreshes the join message countdown
    # and handles timeout cleanup.
    asyncio.create_task(
        _run_join_phase(
            context=context,
            chat_id=chat_id,
            message_id=query.message.message_id,
            state_token=state.token,
            join_seconds=DUEL_JOIN_SECONDS,
            new_token=new_token,
        )
    )


async def _handle_cancel_setup(query, context, chat_id, actor, token, extra):
    state = duel_registry.get_state(chat_id)
    if state is None:
        await query.edit_message_text("Duel no longer active.")
        return

    if not state.is_participant(actor.id):
        raise NotAParticipant()

    await cancel_duel(chat_id, context, reason="cancelled_setup")

    await query.edit_message_text("❌ Duel cancelled.")


async def _handle_join(query, context, chat_id, actor, token, extra):
    state = duel_registry.get_state(chat_id)
    if state is None:
        await query.answer("The duel lobby is no longer active.", show_alert=True)
        return

    # Verify token matches current state (prevents stale button reuse).
    if not duel_registry.verify_callback_token(state, token):
        raise BadToken()

    state_after, all_joined = await player_join(
        chat_id=chat_id,
        user_id=actor.id,
        user_obj=actor,
    )

    new_token = duel_registry.make_callback_token(state_after)

    if all_joined:
        # Both players joined; game is bootstrapped — launch questions.
        await query.edit_message_text(
            f"⚔️ <b>DUEL START!</b>\n\n"
            f"{_safe(state_after.challenger.display_name())} ✅\n"
            f"{_safe(state_after.target.display_name())} ✅\n\n"
            f"⚡ First question coming...",
            parse_mode="HTML",
        )

        asyncio.create_task(
            _launch_duel_questions(chat_id, context, state_after)
        )
    else:
        # Update the join message to show who's joined.
        await query.edit_message_text(
            _join_text(state_after),
            reply_markup=_join_keyboard(new_token),
            parse_mode="HTML",
        )


async def _handle_rematch(query, context, chat_id, actor, token, extra):
    """
    Rematch uses server-side data (bot_data) to get original player IDs,
    NOT callback_data, preventing spoofing.
    """
    if extra is None:
        await query.answer("Invalid rematch data.", show_alert=True)
        return

    try:
        db_game_id = int(extra)
    except ValueError:
        await query.answer("Invalid rematch data.", show_alert=True)
        return

    # Retrieve original player IDs from server-side storage.
    game_data = context.bot_data.get("duel_results", {}).get(db_game_id)
    if not game_data:
        await query.answer("Rematch data expired.", show_alert=True)
        return

    p1_id = game_data["p1_id"]
    p2_id = game_data["p2_id"]

    # Check actor is a participant before doing any work.
    if actor.id not in {p1_id, p2_id}:
        raise NotAParticipant()

    try:
        state = await create_rematch(
            chat_id=chat_id,
            initiator_user=actor,
            p1_id=p1_id,
            p2_id=p2_id,
            db_game_id=db_game_id,
            context=context,
        )
    except DuelAlreadyActive:
        await query.answer("A duel is already in progress.", show_alert=True)
        return
    except NotAParticipant:
        raise
    except Exception as exc:
        logger.exception("Rematch creation failed: %s", exc)
        await query.answer("Could not start rematch. Try /challenge instead.", show_alert=True)
        return

    new_token = duel_registry.make_callback_token(state)

    await query.edit_message_text(
        _challenge_text(state),
        reply_markup=_challenge_keyboard(new_token),
        parse_mode="HTML",
    )

    await record_challenge_message(chat_id, query.message.message_id)


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------


async def _run_join_phase(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    state_token: str,
    join_seconds: int,
    new_token: str,
) -> None:
    """
    Refresh the join lobby countdown every 10 seconds.
    When time runs out, cancel and clean up.
    """
    elapsed = 0
    refresh_every = 10  # seconds

    while elapsed < join_seconds:
        await asyncio.sleep(refresh_every)
        elapsed += refresh_every

        state = duel_registry.get_state(chat_id)
        if state is None or state.token != state_token:
            return  # Duel already concluded.
        if state.phase != DuelPhase.DUEL_JOINING:
            return

        remaining = state.join_remaining_seconds()
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=_join_text(state),
                reply_markup=_join_keyboard(new_token),
                parse_mode="HTML",
            )
        except Exception:
            pass  # Message may have been edited by join press.

        if remaining <= 0:
            break

    # Check if duel expired (not all joined).
    state = duel_registry.get_state(chat_id)
    if state is not None and state.token == state_token and state.phase == DuelPhase.DUEL_JOINING:
        cancelled = await cancel_duel(chat_id, context, reason="timeout")
        if cancelled:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="❌ Duel cancelled — not all players joined in time.",
                )
            except Exception:
                pass


async def _launch_duel_questions(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    state: DuelState,
) -> None:
    """
    Send countdown then hand off to the existing send_question flow.
    Checks that the game still exists before each step.
    """
    from services.game_service import active_games

    for i in range(DUEL_COUNTDOWN_SECONDS, 0, -1):
        # Check game still alive before each sleep.
        if chat_id not in active_games:
            logger.info("Duel game gone during countdown for chat %s", chat_id)
            return
        try:
            await context.bot.send_message(chat_id, f"{i}...")
        except Exception:
            logger.exception("Failed countdown message for chat %s", chat_id)
        await asyncio.sleep(1)

    # Final check before first question.
    if chat_id not in active_games:
        return

    try:
        from handlers.game_play import send_question
        await send_question(chat_id, context)
    except Exception:
        logger.exception("Failed to send first duel question in chat %s", chat_id)
        await cancel_duel(chat_id, context, reason="question_send_failed")
        try:
            await context.bot.send_message(
                chat_id,
                "❌ Failed to start duel. Please try again.",
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Results (called from end_game in handlers/game_results.py)
# ---------------------------------------------------------------------------


async def post_duel_results(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    results: list,
    db_game_id: int,
) -> None:
    """
    Send duel results and store rematch data in bot_data (server-side).
    Called from end_game() instead of the old inline duel results logic.
    """
    from handlers.game_results import format_duel_results

    if len(results) != 2:
        return

    p1 = results[0]
    p2 = results[1]

    # Store server-side so rematch callback can retrieve it without
    # trusting callback_data.
    context.bot_data.setdefault("duel_results", {})[db_game_id] = {
        "p1_id": p1["user_id"],
        "p2_id": p2["user_id"],
    }

    await finish_duel(chat_id)

    # Build a fresh state-less token just for the rematch button.
    # Since state is gone, use a simple opaque key tied to db_game_id.
    import secrets
    result_token = secrets.token_hex(6)
    # We embed db_game_id in the callback; token is just anti-spam here.
    # The server-side check in _handle_rematch validates participation.

    duel_text = format_duel_results(results)

    await context.bot.send_message(
        chat_id=chat_id,
        text=duel_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🔁 Rematch",
                callback_data=_cb("rematch", result_token, str(db_game_id)),
            ),
        ]]),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /stopgame integration (call from existing stop_game handler)
# ---------------------------------------------------------------------------


async def stop_duel_if_active(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    actor_id: int,
) -> bool:
    """
    Returns True if a duel was found and cancelled, False otherwise.
    Permission check (admin/starter) is done by the caller.
    """
    if not duel_registry.has_active_duel(chat_id):
        return False

    cancelled = await cancel_duel(chat_id, context, reason="stopped")
    return cancelled is not None


# ---------------------------------------------------------------------------
# Target resolution (same logic as before, consolidated here)
# ---------------------------------------------------------------------------


async def _resolve_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[User]:
    message = update.effective_message
    chat    = update.effective_chat

    if not message or not chat:
        return None

    # 1. Reply target.
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u if not u.is_bot else None

    # 2. text_mention entity.
    for entity in message.entities or []:
        if entity.type == "text_mention" and getattr(entity, "user", None):
            u = entity.user
            return u if not u.is_bot else None

    # 3. @username argument.
    text = message.text or ""
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None

    raw = parts[1].strip().lstrip("@")
    if not raw or not raw.replace("_", "").isalnum():
        return None

    row = get_player_by_username(raw)
    if not row:
        return None

    try:
        member = await context.bot.get_chat_member(chat.id, row["user_id"])
        u = member.user
        return u if not u.is_bot else None
    except Exception:
        logger.exception("Failed to resolve @%s in chat %s", raw, chat.id)
        return None