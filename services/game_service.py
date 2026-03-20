import asyncio
import math
import time
from typing import Dict

from telegram.ext import ContextTypes

from database import get_random_question
from utils.helpers import safe_delete_message, clickable_name


active_games: Dict[int, dict] = {}
poll_map: Dict[str, dict] = {}
daily_quiz_players: Dict[int, dict] = {}
_game_locks: Dict[int, asyncio.Lock] = {}


def get_game_lock(chat_id: int) -> asyncio.Lock:
    lock = _game_locks.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        _game_locks[chat_id] = lock
    return lock


def cleanup_game_lock(chat_id: int) -> None:
    _game_locks.pop(chat_id, None)


def format_difficulty_name(value: str) -> str:
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
    return {
        "status": "setup",
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
    if join_message_id:
        await safe_delete_message(context.bot, chat_id, join_message_id)

    active_games.pop(chat_id, None)
    cleanup_game_lock(chat_id)


def get_unused_question(game: dict):
    exclude_ids = list(game["used_question_ids"])
    return get_random_question(
        exclude_ids=exclude_ids,
        category=game.get("category"),
        difficulty=game.get("difficulty"),
    )


def get_join_remaining_seconds(game: dict) -> int:
    deadline = game.get("join_deadline")
    if deadline is None:
        return 0
    remaining = math.ceil(deadline - time.monotonic())
    return max(0, remaining)


def add_player_to_game(game: dict, user) -> bool:
    if user.id in game["players"]:
        return False

    game["players"][user.id] = clickable_name(user)
    game["player_objects"][user.id] = user
    game["scores"][user.id] = 0
    game["correct_counts"][user.id] = 0
    game["wrong_counts"][user.id] = 0
    game["answer_times"][user.id] = []
    return True


def mark_game_joining(game: dict, join_seconds: int) -> None:
    game["status"] = "joining"
    game["join_deadline"] = time.monotonic() + join_seconds


def start_next_round(game: dict):
    game["round"] += 1
    current_round = game["round"]
    questions_per_game = game["questions_per_game"]
    should_end = current_round > questions_per_game
    return current_round, questions_per_game, should_end


def prepare_round_state(game: dict, poll_id: str, question_id: int, correct_index: int) -> None:
    game["used_question_ids"].add(question_id)
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
    if user_id not in game["players"]:
        return None

    if user_id in game["answered"]:
        return None

    game["answered"].add(user_id)

    is_correct = bool(option_ids) and option_ids[0] == game["correct"]

    if is_correct:
        points_to_add = correct_points
        got_speed_bonus = False
        elapsed = None

        started_at = game.get("question_started_at")
        if started_at is not None:
            elapsed = time.monotonic() - started_at
            game["answer_times"][user_id].append(elapsed)

            if elapsed <= speed_bonus_seconds:
                points_to_add += speed_bonus_points
                got_speed_bonus = True
                game["speed_bonus_awarded"][user_id] = True
            else:
                game["speed_bonus_awarded"][user_id] = False

        game["scores"][user_id] += points_to_add
        game["correct_counts"][user_id] += 1
    else:
        game["wrong_counts"][user_id] += 1
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
    ranking = sorted(
        game["scores"].items(),
        key=lambda x: (-x[1], x[0]),
    )

    final_results = []

    for position, (user_id, score) in enumerate(ranking, start=1):
        times = game["answer_times"].get(user_id, [])
        avg_time = round(sum(times) / len(times), 2) if times else None

        final_results.append({
            "position": position,
            "user_id": user_id,
            "name": game["players"].get(user_id, f"User {user_id}"),
            "score": score,
            "correct": game["correct_counts"].get(user_id, 0),
            "wrong": game["wrong_counts"].get(user_id, 0),
            "avg_time": avg_time,
        })

    return final_results


def build_results_text(final_results: list[dict]) -> str:
    text = "🏆 Game Results\n\n"

    if not final_results:
        return text + "No players scored any points."

    for row in final_results:
        text += f"{row['position']}. {row['name']} — {row['score']} 🍋\n"

    return text