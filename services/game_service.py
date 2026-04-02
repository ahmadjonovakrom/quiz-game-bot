import asyncio
import math
import time
from collections import defaultdict, deque
from typing import Dict, List

from telegram.ext import ContextTypes

from config import MIN_PLAYERS
from database import get_random_question
from utils.helpers import safe_delete_message

active_games: Dict[int, dict] = {}
poll_map: Dict[str, dict] = {}
daily_quiz_players: Dict[int, dict] = {}
_game_locks: Dict[int, asyncio.Lock] = {}

RECENT_QUESTION_HISTORY_SIZE = 40
recent_questions_by_chat = defaultdict(
    lambda: deque(maxlen=RECENT_QUESTION_HISTORY_SIZE)
)


def _row_value(row, key, default=None):
    if row is None:
        return default
    try:
        value = row[key]
        return default if value is None else value
    except Exception:
        return default


def get_game_lock(chat_id: int) -> asyncio.Lock:
    if not isinstance(chat_id, int):
        raise ValueError(f"chat_id must be int, got {type(chat_id)}")

    if chat_id not in _game_locks:
        _game_locks[chat_id] = asyncio.Lock()

    return _game_locks[chat_id]


def cleanup_game_lock(chat_id: int) -> None:
    _game_locks.pop(chat_id, None)


def get_recent_question_ids(chat_id: int) -> List[int]:
    if chat_id is None:
        return []
    return list(recent_questions_by_chat.get(chat_id, []))


def remember_question(chat_id: int, question_id: int):
    if chat_id is None or question_id is None:
        return
    if not isinstance(question_id, int):
        return
    recent_questions_by_chat[chat_id].append(question_id)


def format_difficulty_name(value: str) -> str:
    if not isinstance(value, str):
        return ""

    mapping = {
        "easy": "Easy",
        "medium": "Medium",
        "hard": "Hard",
        "mixed": "Mixed",
    }
    return mapping.get(str(value).lower(), str(value).replace("_", " ").title())


def create_new_game_data(
    started_by: int,
    questions_per_game: int,
    category: str,
    difficulty: str,
) -> dict:
    if not isinstance(questions_per_game, int) or questions_per_game < 1:
        raise ValueError("questions_per_game must be a positive integer")

    return {
        "status": "setup",
        "mode": "solo",
        "max_players": None,
        "started_by": started_by,
        "players": {},
        "player_objects": {},
        "scores": {},
        "round": 0,
        "answered": set(),
        "current_poll_id": None,
        "correct": None,
        "join_message_id": None,
        "join_deadline": None,
        "join_seconds": None,
        "postpone_count": 0,
        "max_postpones": 2,
        "postpone_seconds": 30,
        "used_question_ids": set(),
        "question_started_at": None,
        "speed_bonus_awarded": {},
        "correct_counts": {},
        "wrong_counts": {},
        "answer_times": {},
        "db_game_id": None,
        "questions_per_game": questions_per_game,
        "category": category,
        "difficulty": difficulty,
        "min_players": MIN_PLAYERS,
        "chat_id": None,
    }


def get_existing_game_message(game: dict) -> str:
    status = game.get("status")
    if status == "setup":
        return "Game setup is already in progress."
    if status == "joining":
        return "A game is already waiting for players."
    if status == "running":
        return "A game is already running."
    if status == "ending":
        return "A game is ending right now."
    return "A game already exists in this group."


async def clear_game(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = active_games.get(chat_id)
    if not game:
        cleanup_game_lock(chat_id)
        return

    current_poll_id = game.get("current_poll_id")
    if current_poll_id:
        poll_map.pop(current_poll_id, None)

    join_message_id = game.get("join_message_id")
    if join_message_id and getattr(context, "bot", None):
        await safe_delete_message(context.bot, chat_id, join_message_id)

    active_games.pop(chat_id, None)
    cleanup_game_lock(chat_id)


def get_unused_question(game: dict):
    used_ids = list(game.get("used_question_ids", set()))
    chat_id = game.get("chat_id")

    recent_ids = get_recent_question_ids(chat_id) if chat_id is not None else []
    exclude_ids = list(dict.fromkeys(used_ids + recent_ids))

    category = game.get("category")
    difficulty = game.get("difficulty")

    question = get_random_question(
        exclude_ids=exclude_ids,
        category=category,
        difficulty=difficulty,
    )

    if not question:
        question = get_random_question(
            exclude_ids=used_ids,
            category=category,
            difficulty=difficulty,
        )

    if not question:
        question = get_random_question(
            category=category,
            difficulty=difficulty,
        )

    if not question:
        return None

    q_id = _row_value(question, "id")
    if q_id is None:
        return None

    used_question_ids = game.get("used_question_ids")
    if not isinstance(used_question_ids, set):
        used_question_ids = set()
        game["used_question_ids"] = used_question_ids

    used_question_ids.add(q_id)

    if chat_id is not None and isinstance(q_id, int):
        remember_question(chat_id, q_id)

    return question


def get_join_remaining_seconds(game: dict) -> int:
    deadline = game.get("join_deadline")
    if deadline is None:
        return 0
    remaining = math.ceil(deadline - time.monotonic())
    return max(0, remaining)


def add_player_to_game(game: dict, user) -> bool:
    if not hasattr(user, "id"):
        return False

    players = game.get("players")
    if not isinstance(players, dict):
        players = {}
        game["players"] = players

    player_objects = game.get("player_objects")
    if not isinstance(player_objects, dict):
        player_objects = {}
        game["player_objects"] = player_objects

    scores = game.get("scores")
    if not isinstance(scores, dict):
        scores = {}
        game["scores"] = scores

    correct_counts = game.get("correct_counts")
    if not isinstance(correct_counts, dict):
        correct_counts = {}
        game["correct_counts"] = correct_counts

    wrong_counts = game.get("wrong_counts")
    if not isinstance(wrong_counts, dict):
        wrong_counts = {}
        game["wrong_counts"] = wrong_counts

    answer_times = game.get("answer_times")
    if not isinstance(answer_times, dict):
        answer_times = {}
        game["answer_times"] = answer_times

    max_players = game.get("max_players")

    if user.id in players:
        return False

    if max_players is not None:
        if not isinstance(max_players, int) or max_players < 1:
            return False
        if len(players) >= max_players:
            return False

    players[user.id] = {
        "full_name": getattr(user, "full_name", None),
        "username": getattr(user, "username", None),
        "first_name": getattr(user, "first_name", None),
    }
    player_objects[user.id] = user
    scores[user.id] = 0
    correct_counts[user.id] = 0
    wrong_counts[user.id] = 0
    answer_times[user.id] = []

    return True


def mark_game_joining(game: dict, join_seconds: int) -> None:
    game["status"] = "joining"
    game["join_seconds"] = join_seconds
    game["join_deadline"] = time.monotonic() + join_seconds


def start_next_round(game: dict):
    game["round"] = int(game.get("round", 0)) + 1
    current_round = game["round"]
    questions_per_game = int(game.get("questions_per_game", 0))
    should_end = current_round > questions_per_game
    return current_round, questions_per_game, should_end


def prepare_round_state(game: dict, poll_id: str, question_id: int, correct_index: int) -> None:
    used_question_ids = game.get("used_question_ids")
    if not isinstance(used_question_ids, set):
        used_question_ids = set()
        game["used_question_ids"] = used_question_ids

    used_question_ids.add(question_id)
    game["correct"] = correct_index
    game["answered"] = set()
    game["speed_bonus_awarded"] = {}
    game["question_started_at"] = time.monotonic()
    game["current_poll_id"] = poll_id


def apply_poll_answer(
    game: dict,
    user_id: int,
    option_ids: list[int],
    correct_points: int,
    speed_bonus_seconds: int,
    speed_bonus_points: int,
):
    players = game.get("players", {})
    answered = game.get("answered")
    if not isinstance(answered, set):
        answered = set()
        game["answered"] = answered

    if user_id not in players:
        return None

    if user_id in answered:
        return None

    answered.add(user_id)

    correct_index = game.get("correct")
    is_correct = bool(option_ids) and option_ids[0] == correct_index

    scores = game.get("scores", {})
    correct_counts = game.get("correct_counts", {})
    wrong_counts = game.get("wrong_counts", {})
    answer_times = game.get("answer_times", {})
    speed_bonus_awarded = game.get("speed_bonus_awarded", {})

    game["scores"] = scores
    game["correct_counts"] = correct_counts
    game["wrong_counts"] = wrong_counts
    game["answer_times"] = answer_times
    game["speed_bonus_awarded"] = speed_bonus_awarded

    if user_id not in answer_times:
        answer_times[user_id] = []

    if is_correct:
        points_to_add = correct_points
        got_speed_bonus = False
        elapsed = None

        started_at = game.get("question_started_at")
        if started_at is not None:
            elapsed = time.monotonic() - started_at
            answer_times[user_id].append(elapsed)

            if elapsed <= speed_bonus_seconds:
                points_to_add += speed_bonus_points
                got_speed_bonus = True
                speed_bonus_awarded[user_id] = True
            else:
                speed_bonus_awarded[user_id] = False

        scores[user_id] = scores.get(user_id, 0) + points_to_add
        correct_counts[user_id] = correct_counts.get(user_id, 0) + 1
    else:
        wrong_counts[user_id] = wrong_counts.get(user_id, 0) + 1
        points_to_add = 0
        got_speed_bonus = False
        elapsed = None

    return {
        "is_correct": is_correct,
        "points_to_add": points_to_add,
        "got_speed_bonus": got_speed_bonus,
        "elapsed": elapsed,
    }


def build_final_results(game: dict) -> list[dict]:
    scores = game.get("scores", {})
    players = game.get("players", {})
    correct_counts = game.get("correct_counts", {})
    wrong_counts = game.get("wrong_counts", {})
    answer_times = game.get("answer_times", {})

    ranking = sorted(
        scores.items(),
        key=lambda x: (-x[1], x[0]),
    )

    final_results = []

    for position, (user_id, score) in enumerate(ranking, start=1):
        times = answer_times.get(user_id, [])
        avg_time = round(sum(times) / len(times), 2) if times else None

        player = players.get(user_id, {})

        name = (
            player.get("full_name")
            or player.get("first_name")
            or player.get("username")
            or f"User {user_id}"
        )

        final_results.append({
            "position": position,
            "user_id": user_id,
            "name": name,
            "points": score,
            "correct": correct_counts.get(user_id, 0),
            "wrong": wrong_counts.get(user_id, 0),
            "avg_time": avg_time,
        })

    return final_results


def build_results_text(results):
    text = "🏆 Final Results\n\n"

    for row in results:
        text += f"{row['position']}. {row['name']} — {row['points']} 🍋\n"

    return textupdate