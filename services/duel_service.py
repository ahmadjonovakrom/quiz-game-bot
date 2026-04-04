"""
services/duel_service.py

Business logic layer for duels.  Handlers call this; this calls duel_registry
and game_service.  No telegram objects imported here — only IDs and primitives
so this layer is fully unit-testable.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Tuple

from config import DEFAULT_QUESTIONS_PER_GAME
from database import create_game, ensure_player, ensure_group_player
from services.duel_state import (
    DuelPlayer,
    DuelPhase,
    DuelRegistry,
    DuelState,
    DuelAlreadyActive,
    InvalidTransition,
    NotAParticipant,
    AlreadyJoined,
    BadToken,
    duel_registry,
)
from services.game_service import (
    active_games,
    create_new_game_data,
    add_player_to_game,
    get_game_lock,
    cleanup_game_lock,
    poll_map,
)
from utils.helpers import safe_delete_message

logger = logging.getLogger(__name__)

CHALLENGE_TIMEOUT_SECONDS = 60
DUEL_JOIN_SECONDS = 30          # How long after Accept both players have to press Join.
DUEL_COUNTDOWN_SECONDS = 3      # Countdown before first question.


# ---------------------------------------------------------------------------
# Player construction helpers
# ---------------------------------------------------------------------------


def make_duel_player(user) -> DuelPlayer:
    """Build a DuelPlayer from a telegram User object."""
    return DuelPlayer(
        user_id=user.id,
        full_name=user.full_name or "",
        username=user.username,
    )


# ---------------------------------------------------------------------------
# Challenge lifecycle
# ---------------------------------------------------------------------------


async def create_challenge(
    chat_id: int,
    challenger_user,
    target_user,
) -> DuelState:
    """
    Create a pending challenge.
    Raises DuelAlreadyActive if a duel is already in progress for the chat.
    Raises ValueError if challenger == target or target is a bot.
    """
    if challenger_user.id == target_user.id:
        raise ValueError("Cannot challenge yourself.")
    if getattr(target_user, "is_bot", False):
        raise ValueError("Cannot challenge a bot.")

    challenger = make_duel_player(challenger_user)
    target = make_duel_player(target_user)

    state = await duel_registry.create_challenge(
        chat_id=chat_id,
        challenger=challenger,
        target=target,
        expire_seconds=CHALLENGE_TIMEOUT_SECONDS,
        expire_callback=_on_challenge_expired,
    )
    return state


async def _on_challenge_expired(chat_id: int, state: DuelState) -> None:
    """Called by the registry expiry task after lock is released."""
    logger.info(
        "Challenge expired in chat %s (challenger=%s target=%s)",
        chat_id,
        state.challenger.user_id,
        state.target.user_id,
    )
    # Caller (handler) is responsible for editing the Telegram message.
    # We emit an event here; in a larger system this would be a pub/sub signal.
    # For now, the expiry editing is handled inside the handler via a stored
    # message_id on the state snapshot returned to the caller.


async def record_challenge_message(chat_id: int, message_id: int) -> None:
    """Store the Telegram message ID so the expiry callback can edit it."""
    await duel_registry.set_challenge_message_id(chat_id, message_id)


async def decline_challenge(
    chat_id: int,
    actor_id: int,
    token: str,
) -> DuelState:
    return await duel_registry.decline_challenge(chat_id, actor_id, token)


async def accept_challenge(
    chat_id: int,
    actor_id: int,
    token: str,
) -> DuelState:
    return await duel_registry.accept_challenge(chat_id, actor_id, token)


# ---------------------------------------------------------------------------
# Setup phase
# ---------------------------------------------------------------------------


async def configure_duel(
    chat_id: int,
    questions_per_game: int,
    setup_message_id: int,
) -> DuelState:
    return await duel_registry.configure_setup(
        chat_id, questions_per_game, setup_message_id
    )


# ---------------------------------------------------------------------------
# Joining phase
# ---------------------------------------------------------------------------


async def open_duel_lobby(
    chat_id: int,
    join_message_id: int,
    join_seconds: int = DUEL_JOIN_SECONDS,
) -> DuelState:
    """
    Transition to DUEL_JOINING.  Challenger is auto-joined.
    Schedules timeout task.
    """
    state = await duel_registry.start_joining(
        chat_id=chat_id,
        join_seconds=join_seconds,
        join_message_id=join_message_id,
    )
    # Schedule a join-timeout watcher.
    asyncio.create_task(
        _watch_join_timeout(chat_id, state.token, join_seconds)
    )
    return state


async def _watch_join_timeout(
    chat_id: int,
    token: str,
    join_seconds: int,
) -> None:
    """
    Wait for join window; if not all joined, cancel the duel.
    Token check prevents stale tasks from acting on replaced state.
    """
    await asyncio.sleep(join_seconds + 1)

    state = duel_registry.get_state(chat_id)
    if state is None or state.token != token:
        return
    if state.phase != DuelPhase.DUEL_JOINING:
        return

    cancelled = await duel_registry.cancel_joining(chat_id, reason="timeout")
    if cancelled:
        logger.info("Duel join timed out in chat %s", chat_id)
        # The handler is responsible for sending the cancellation message.
        # We store enough on the state snapshot for it to do so.


async def player_join(
    chat_id: int,
    user_id: int,
    user_obj,
) -> Tuple[DuelState, bool]:
    """
    Record a join press.
    Returns (state, all_joined).
    Raises AlreadyJoined, NotAParticipant, InvalidTransition.

    If all_joined is True, the game_service active_games entry has already
    been created and set to status="running"; caller should proceed to
    start questions.
    """
    # Persist player to DB before touching state.
    try:
        ensure_player(user_obj)
        if chat_id < 0:
            ensure_group_player(chat_id, user_obj)
    except Exception:
        logger.exception("Failed to ensure player %s on duel join", user_id)

    state = await duel_registry.player_join(chat_id, user_id)
    all_joined = state.phase == DuelPhase.DUEL_RUNNING

    if all_joined:
        # Bridge into existing game_service so quiz logic is untouched.
        await _bootstrap_game_service(chat_id, state)

    return state, all_joined


async def _bootstrap_game_service(chat_id: int, state: DuelState) -> None:
    """
    Create an entry in game_service.active_games so that the existing
    send_question / receive_poll_answer / end_game flow works unchanged.
    This is the ONLY place where duel_service touches game_service.
    """
    lock = get_game_lock(chat_id)
    async with lock:
        # Guard: if somehow active_games already has this chat (shouldn't happen),
        # do not overwrite.
        if chat_id in active_games:
            logger.warning(
                "active_games already has entry for chat %s during duel bootstrap",
                chat_id,
            )
            return

        game = create_new_game_data(
            started_by=state.challenger.user_id,
            questions_per_game=state.questions_per_game,
            category="mixed",
            difficulty="mixed",
        )
        game.update({
            "chat_id": chat_id,
            "mode": "duel",
            "status": "running",          # Already running — no joining phase here.
            "min_players": 2,
            "max_players": 2,
        })

        # Add both players using the canonical helper.
        # We need telegram User objects; retrieve from the player_objects we
        # stashed during accept — but game_service needs full User objects.
        # Solution: store lightweight player dicts; game_service only uses
        # .id, .full_name, .username from user objects (duck-typed).
        for player in state.both_players:
            _duck_user = _DuckUser(player)
            add_player_to_game(game, _duck_user)

        try:
            db_game_id = create_game(
                chat_id=chat_id,
                total_players=2,
                total_rounds=state.questions_per_game,
                status="running",
            )
            game["db_game_id"] = db_game_id
        except Exception:
            logger.exception("Failed to create DB game record for duel in chat %s", chat_id)

        active_games[chat_id] = game

    # Persist DB game ID back to duel state for later use in finish_duel().
    if game.get("db_game_id"):
        await duel_registry.attach_db_game(chat_id, game["db_game_id"])


class _DuckUser:
    """
    Minimal duck-type wrapper around DuelPlayer so game_service.add_player_to_game
    works without importing telegram.User here.
    """
    def __init__(self, player: DuelPlayer) -> None:
        self.id = player.user_id
        self.full_name = player.full_name
        self.username = player.username
        self.first_name = player.full_name.split()[0] if player.full_name else ""


# ---------------------------------------------------------------------------
# Running phase — finish / cancel
# ---------------------------------------------------------------------------


async def finish_duel(chat_id: int) -> Optional[DuelState]:
    """
    Called by end_game() hook (or directly) when quiz ends normally.
    Cleans up duel_registry; game_service cleans up active_games separately.
    """
    return await duel_registry.finish_duel(chat_id)


async def cancel_duel(
    chat_id: int,
    context,
    reason: str = "stopped",
) -> Optional[DuelState]:
    """
    Cancel at any cancellable phase.  Cleans up both registries.
    """
    state = duel_registry.get_state(chat_id)
    if state is None:
        return None

    phase = state.phase

    if phase == DuelPhase.CHALLENGE_PENDING:
        # Cancel via decline path without token (admin/timeout override).
        async with duel_registry._get_lock(chat_id):
            s = duel_registry._states.get(chat_id)
            if s and s.phase == DuelPhase.CHALLENGE_PENDING:
                if s._expire_task and not s._expire_task.done():
                    s._expire_task.cancel()
                s.phase = DuelPhase.CANCELLED
                s.cancellation_reason = reason
                duel_registry._states.pop(chat_id, None)
        duel_registry._release_lock(chat_id)
        return s

    if phase == DuelPhase.DUEL_JOINING:
        cancelled = await duel_registry.cancel_joining(chat_id, reason)
        if cancelled:
            join_msg = cancelled.join_message_id
            if join_msg:
                await safe_delete_message(context.bot, chat_id, join_msg)
        return cancelled

    if phase == DuelPhase.DUEL_RUNNING:
        cancelled = await duel_registry.cancel_running(chat_id, reason)
        if cancelled:
            # Also clean up game_service.
            lock = get_game_lock(chat_id)
            async with lock:
                game = active_games.pop(chat_id, None)
                if game:
                    poll_id = game.get("current_poll_id")
                    if poll_id:
                        poll_map.pop(poll_id, None)
            cleanup_game_lock(chat_id)
        return cancelled

    return None


# ---------------------------------------------------------------------------
# Rematch
# ---------------------------------------------------------------------------


async def create_rematch(
    chat_id: int,
    initiator_user,
    p1_id: int,
    p2_id: int,
    db_game_id: int,
    context,
) -> None:
    """
    Validate and start a rematch.

    p1_id / p2_id come from bot_data (server-side), NOT from callback_data,
    eliminating the spoofing vector described in the audit.

    Raises DuelAlreadyActive, NotAParticipant.
    """
    # Only original participants can initiate.
    if initiator_user.id not in {p1_id, p2_id}:
        raise NotAParticipant("Rematch can only be initiated by original players.")

    if duel_registry.has_active_duel(chat_id):
        raise DuelAlreadyActive("A duel is already in progress.")

    # Fetch the other player's info from Telegram.
    other_id = p2_id if initiator_user.id == p1_id else p1_id

    try:
        other_member = await context.bot.get_chat_member(chat_id, other_id)
        other_user = other_member.user
    except Exception:
        raise DuelError(f"Could not retrieve opponent (user_id={other_id}).")

    # Create a new challenge from initiator to other player.
    # This reuses the full challenge flow (Accept/Decline), which is the
    # correct UX: rematches should require explicit acceptance.
    state = await create_challenge(
        chat_id=chat_id,
        challenger_user=initiator_user,
        target_user=other_user,
    )
    return state


class DuelError(Exception):
    pass