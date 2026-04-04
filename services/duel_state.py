"""
services/duel_state.py

Single source of truth for duel lifecycle state.

State machine transitions (only these are legal):
  IDLE (no entry) ──► CHALLENGE_PENDING  via create_challenge()
  CHALLENGE_PENDING ──► CANCELLED        via cancel_challenge()  [timeout / decline]
  CHALLENGE_PENDING ──► DUEL_SETUP       via accept_challenge()
  DUEL_SETUP        ──► DUEL_JOINING     via start_joining()
  DUEL_JOINING      ──► DUEL_RUNNING     via start_running()
  DUEL_JOINING      ──► CANCELLED        via cancel_joining()    [timeout / stop]
  DUEL_RUNNING      ──► FINISHED         via finish_duel()
  DUEL_RUNNING      ──► CANCELLED        via cancel_running()    [/stopgame]

Only one DuelState may exist per chat_id at any time.
All mutations go through DuelRegistry which holds per-chat asyncio.Lock instances.
"""

from __future__ import annotations

import asyncio
import enum
import hmac
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional, Set

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DuelPhase(enum.Enum):
    CHALLENGE_PENDING = "challenge_pending"
    DUEL_SETUP        = "duel_setup"
    DUEL_JOINING      = "duel_joining"
    DUEL_RUNNING      = "duel_running"
    FINISHED          = "finished"
    CANCELLED         = "cancelled"


# Phases that count as "a duel is in progress" for has_active_duel() purposes.
ACTIVE_PHASES: FrozenSet[DuelPhase] = frozenset({
    DuelPhase.CHALLENGE_PENDING,
    DuelPhase.DUEL_SETUP,
    DuelPhase.DUEL_JOINING,
    DuelPhase.DUEL_RUNNING,
})

# ---------------------------------------------------------------------------
# Immutable player snapshot (captured at challenge time, not mutable after)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuelPlayer:
    user_id: int
    full_name: str
    username: Optional[str]

    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.full_name or f"User {self.user_id}"


# ---------------------------------------------------------------------------
# Main state object
# ---------------------------------------------------------------------------


@dataclass
class DuelState:
    # ── identity ──────────────────────────────────────────────────────────
    chat_id: int
    challenger: DuelPlayer
    target: DuelPlayer

    # ── lifecycle ─────────────────────────────────────────────────────────
    phase: DuelPhase = DuelPhase.CHALLENGE_PENDING
    created_at: float = field(default_factory=time.monotonic)

    # ── challenge-phase data ───────────────────────────────────────────────
    # Message ID of the Accept/Decline message so we can edit it later.
    challenge_message_id: Optional[int] = None
    # Opaque token embedded in callback_data; verified server-side.
    token: str = field(default_factory=lambda: secrets.token_hex(8))
    # asyncio.Task for expiry; cancelled on accept/decline.
    _expire_task: Optional[asyncio.Task] = field(default=None, repr=False)

    # ── setup-phase data ──────────────────────────────────────────────────
    questions_per_game: int = 10
    setup_message_id: Optional[int] = None

    # ── joining-phase data ────────────────────────────────────────────────
    join_message_id: Optional[int] = None
    join_deadline: Optional[float] = None
    # Set of user_ids that have pressed Join (challenger auto-joined).
    joined_user_ids: Set[int] = field(default_factory=set)

    # ── running-phase data ────────────────────────────────────────────────
    db_game_id: Optional[int] = None
    # Reference into existing game_service.active_games (unchanged system).
    # We store the key so duel_state and game_service stay loosely coupled.
    active_game_chat_id: Optional[int] = None

    # ── terminal-phase data ───────────────────────────────────────────────
    cancellation_reason: Optional[str] = None

    # ------------------------------------------------------------------
    # Convenience helpers (read-only, no side effects)
    # ------------------------------------------------------------------

    @property
    def both_players(self) -> tuple[DuelPlayer, DuelPlayer]:
        return self.challenger, self.target

    @property
    def player_ids(self) -> Set[int]:
        return {self.challenger.user_id, self.target.user_id}

    def is_participant(self, user_id: int) -> bool:
        return user_id in self.player_ids

    def has_joined(self, user_id: int) -> bool:
        return user_id in self.joined_user_ids

    def all_joined(self) -> bool:
        return self.player_ids == self.joined_user_ids

    def join_remaining_seconds(self) -> int:
        if self.join_deadline is None:
            return 0
        import math
        return max(0, math.ceil(self.join_deadline - time.monotonic()))

    # ------------------------------------------------------------------
    # Internal transition helpers (called only by DuelRegistry methods)
    # ------------------------------------------------------------------

    def _assert_phase(self, *expected: DuelPhase) -> None:
        if self.phase not in expected:
            raise InvalidTransition(
                f"Expected phase(s) {[p.value for p in expected]}, "
                f"got {self.phase.value}"
            )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DuelError(Exception):
    """Base class for duel-related errors."""


class DuelAlreadyActive(DuelError):
    """Raised when a duel already exists for a chat."""


class InvalidTransition(DuelError):
    """Raised when a state transition is illegal."""


class NotAParticipant(DuelError):
    """Raised when a non-participant tries to act on a duel."""


class AlreadyJoined(DuelError):
    """Raised on duplicate join attempt."""


class BadToken(DuelError):
    """Raised when callback token verification fails."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class DuelRegistry:
    """
    Thread-safe (asyncio) store for one DuelState per chat.

    All public methods acquire the per-chat lock before reading or writing
    state.  Callers must NOT hold the lock themselves; all mutations go
    through this class.
    """

    def __init__(self) -> None:
        # chat_id → DuelState
        self._states: Dict[int, DuelState] = {}
        # chat_id → asyncio.Lock  (created lazily, never deleted until terminal)
        self._locks: Dict[int, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Lock management
    # ------------------------------------------------------------------

    def _get_lock(self, chat_id: int) -> asyncio.Lock:
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    def _release_lock(self, chat_id: int) -> None:
        """Drop the lock once a terminal state is reached."""
        self._locks.pop(chat_id, None)

    # ------------------------------------------------------------------
    # Token verification
    # ------------------------------------------------------------------

    @staticmethod
    def _sign(token: str, chat_id: int, challenger_id: int, target_id: int) -> str:
        """
        Produce a short HMAC tag that is embedded in callback_data.
        Callers embed the returned tag; verification re-computes and compares.
        Protects against spoofed rematch/challenge callbacks.
        """
        msg = f"{token}:{chat_id}:{challenger_id}:{target_id}".encode()
        return hmac.new(token.encode(), msg, hashlib.sha256).hexdigest()[:12]

    def make_callback_token(self, state: DuelState) -> str:
        """Return a short opaque string safe to embed in callback_data."""
        return self._sign(
            state.token,
            state.chat_id,
            state.challenger.user_id,
            state.target.user_id,
        )

    def verify_callback_token(
        self,
        state: DuelState,
        token_from_callback: str,
    ) -> bool:
        expected = self.make_callback_token(state)
        return hmac.compare_digest(expected, token_from_callback)

    # ------------------------------------------------------------------
    # Read helpers (safe outside lock — return snapshots or booleans)
    # ------------------------------------------------------------------

    def has_active_duel(self, chat_id: int) -> bool:
        state = self._states.get(chat_id)
        return state is not None and state.phase in ACTIVE_PHASES

    def get_state(self, chat_id: int) -> Optional[DuelState]:
        """
        Return current state (may be None).
        Caller MUST NOT mutate the returned object directly.
        """
        return self._states.get(chat_id)

    # ------------------------------------------------------------------
    # CHALLENGE_PENDING phase
    # ------------------------------------------------------------------

    async def create_challenge(
        self,
        chat_id: int,
        challenger: DuelPlayer,
        target: DuelPlayer,
        expire_seconds: int,
        expire_callback,          # async callable(chat_id) — called on timeout
    ) -> DuelState:
        """
        Create a pending challenge.  Raises DuelAlreadyActive if any active
        duel already exists for this chat.
        """
        async with self._get_lock(chat_id):
            if self.has_active_duel(chat_id):
                existing = self._states[chat_id]
                raise DuelAlreadyActive(
                    f"Duel already in phase {existing.phase.value}"
                )

            state = DuelState(
                chat_id=chat_id,
                challenger=challenger,
                target=target,
            )
            self._states[chat_id] = state

            # Schedule expiry task AFTER state is committed so that if the
            # task fires immediately it will find valid state.
            state._expire_task = asyncio.create_task(
                self._run_expiry(chat_id, state.token, expire_seconds, expire_callback)
            )

            return state

    async def _run_expiry(
        self,
        chat_id: int,
        token: str,
        expire_seconds: int,
        expire_callback,
    ) -> None:
        """
        Background task: wait, then atomically cancel challenge if it hasn't
        already transitioned.  Uses token to detect stale tasks.
        """
        try:
            await asyncio.sleep(expire_seconds)
        except asyncio.CancelledError:
            return

        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            # Stale task: state replaced or token mismatch means challenge
            # was already accepted / cancelled.
            if state is None or state.token != token:
                return
            if state.phase != DuelPhase.CHALLENGE_PENDING:
                return

            state.phase = DuelPhase.CANCELLED
            state.cancellation_reason = "timeout"
            self._states.pop(chat_id, None)

        # Notify outside the lock (network I/O).
        try:
            await expire_callback(chat_id, state)
        except Exception:
            pass
        finally:
            self._release_lock(chat_id)

    async def set_challenge_message_id(
        self,
        chat_id: int,
        message_id: int,
    ) -> None:
        """Store the Telegram message ID of the challenge invite."""
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state and state.phase == DuelPhase.CHALLENGE_PENDING:
                state.challenge_message_id = message_id

    async def decline_challenge(
        self,
        chat_id: int,
        actor_id: int,
        token_from_callback: str,
    ) -> DuelState:
        """
        Decline a pending challenge.
        actor_id must be the target; token must match.
        Returns the (now-cancelled) state for use in UI updates.
        """
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state is None:
                raise DuelError("No active challenge.")
            state._assert_phase(DuelPhase.CHALLENGE_PENDING)

            if not self.verify_callback_token(state, token_from_callback):
                raise BadToken("Challenge token mismatch.")

            if actor_id != state.target.user_id:
                raise NotAParticipant("Only the target can decline.")

            # Cancel expiry task before changing phase.
            if state._expire_task and not state._expire_task.done():
                state._expire_task.cancel()

            state.phase = DuelPhase.CANCELLED
            state.cancellation_reason = "declined"
            self._states.pop(chat_id, None)

        self._release_lock(chat_id)
        return state

    async def accept_challenge(
        self,
        chat_id: int,
        actor_id: int,
        token_from_callback: str,
    ) -> DuelState:
        """
        Accept a pending challenge, transitioning to DUEL_SETUP.
        actor_id must be the target; token must match.
        """
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state is None:
                raise DuelError("No active challenge.")
            state._assert_phase(DuelPhase.CHALLENGE_PENDING)

            if not self.verify_callback_token(state, token_from_callback):
                raise BadToken("Challenge token mismatch.")

            if actor_id != state.target.user_id:
                raise NotAParticipant("Only the target can accept.")

            # Cancel expiry before phase change.
            if state._expire_task and not state._expire_task.done():
                state._expire_task.cancel()
            state._expire_task = None

            state.phase = DuelPhase.DUEL_SETUP
            return state

    # ------------------------------------------------------------------
    # DUEL_SETUP phase
    # ------------------------------------------------------------------

    async def configure_setup(
        self,
        chat_id: int,
        questions_per_game: int,
        setup_message_id: int,
    ) -> DuelState:
        """Store setup choices made by players in the setup UI."""
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state is None:
                raise DuelError("No duel state found.")
            state._assert_phase(DuelPhase.DUEL_SETUP)
            state.questions_per_game = questions_per_game
            state.setup_message_id = setup_message_id
            return state

    async def start_joining(
        self,
        chat_id: int,
        join_seconds: int,
        join_message_id: int,
    ) -> DuelState:
        """
        Transition DUEL_SETUP → DUEL_JOINING.
        Challenger is auto-joined.
        """
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state is None:
                raise DuelError("No duel state found.")
            state._assert_phase(DuelPhase.DUEL_SETUP)

            state.phase = DuelPhase.DUEL_JOINING
            state.join_message_id = join_message_id
            state.join_deadline = time.monotonic() + join_seconds
            # Challenger is automatically in.
            state.joined_user_ids.add(state.challenger.user_id)
            return state

    # ------------------------------------------------------------------
    # DUEL_JOINING phase
    # ------------------------------------------------------------------

    async def player_join(
        self,
        chat_id: int,
        user_id: int,
    ) -> DuelState:
        """
        Record that user_id pressed Join.
        Raises NotAParticipant if user is not challenger/target.
        Raises AlreadyJoined if they already pressed Join.
        Returns state; caller checks state.all_joined() to decide whether
        to start the game.
        """
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state is None:
                raise DuelError("No duel state found.")
            state._assert_phase(DuelPhase.DUEL_JOINING)

            if not state.is_participant(user_id):
                raise NotAParticipant("You are not part of this duel.")

            if state.has_joined(user_id):
                raise AlreadyJoined("Already joined.")

            state.joined_user_ids.add(user_id)

            if state.all_joined():
                # Atomically transition to RUNNING so no second caller
                # can also see all_joined() == True and double-start.
                state.phase = DuelPhase.DUEL_RUNNING

            return state

    async def cancel_joining(
        self,
        chat_id: int,
        reason: str = "timeout",
    ) -> Optional[DuelState]:
        """Cancel a DUEL_JOINING duel (timeout or /stopgame)."""
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state is None:
                return None
            if state.phase != DuelPhase.DUEL_JOINING:
                return None

            state.phase = DuelPhase.CANCELLED
            state.cancellation_reason = reason
            self._states.pop(chat_id, None)

        self._release_lock(chat_id)
        return state

    # ------------------------------------------------------------------
    # DUEL_RUNNING phase
    # ------------------------------------------------------------------

    async def attach_db_game(
        self,
        chat_id: int,
        db_game_id: int,
    ) -> None:
        """Store the DB game ID once the game record is created."""
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state and state.phase == DuelPhase.DUEL_RUNNING:
                state.db_game_id = db_game_id

    async def finish_duel(self, chat_id: int) -> Optional[DuelState]:
        """Transition DUEL_RUNNING → FINISHED and remove from registry."""
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state is None:
                return None
            if state.phase != DuelPhase.DUEL_RUNNING:
                return None

            state.phase = DuelPhase.FINISHED
            self._states.pop(chat_id, None)

        self._release_lock(chat_id)
        return state

    async def cancel_running(
        self,
        chat_id: int,
        reason: str = "stopped",
    ) -> Optional[DuelState]:
        """Cancel a DUEL_RUNNING duel (/stopgame)."""
        async with self._get_lock(chat_id):
            state = self._states.get(chat_id)
            if state is None:
                return None
            if state.phase != DuelPhase.DUEL_RUNNING:
                return None

            state.phase = DuelPhase.CANCELLED
            state.cancellation_reason = reason
            self._states.pop(chat_id, None)

        self._release_lock(chat_id)
        return state

    # ------------------------------------------------------------------
    # Global helpers
    # ------------------------------------------------------------------

    def active_count(self) -> int:
        return sum(
            1 for s in self._states.values() if s.phase in ACTIVE_PHASES
        )


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere instead of bare dicts.
# ---------------------------------------------------------------------------
duel_registry = DuelRegistry()