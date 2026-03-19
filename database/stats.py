from contextlib import closing
from typing import Optional

from .connection import get_conn
from .games import get_total_games, get_total_groups
from .players import get_total_players, get_total_users_count
from .questions import get_question_count, get_total_questions_count


def get_group_top_players(chat_id: int, limit: int = 10):
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT
                user_id,
                username,
                full_name,
                total_points AS points,
                correct_answers,
                games_won
            FROM group_scores
            WHERE chat_id = ?
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
            LIMIT ?
        """, (chat_id, limit)).fetchall()


def get_group_user_rank(chat_id: int, user_id: int) -> Optional[dict]:
    with closing(get_conn()) as conn:
        me = conn.execute("""
            SELECT
                user_id,
                username,
                full_name,
                total_points AS points,
                correct_answers,
                games_won
            FROM group_scores
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id)).fetchone()

        if not me:
            return None

        rows = conn.execute("""
            SELECT user_id
            FROM group_scores
            WHERE chat_id = ?
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
        """, (chat_id,)).fetchall()

        for index, row in enumerate(rows, start=1):
            if row["user_id"] == user_id:
                return {
                    "rank": index,
                    "points": me["points"],
                    "full_name": me["full_name"],
                    "username": me["username"],
                }

        return None


__all__ = [
    "get_total_games",
    "get_total_groups",
    "get_total_players",
    "get_total_users_count",
    "get_question_count",
    "get_total_questions_count",
    "get_group_top_players",
    "get_group_user_rank",
]