from contextlib import closing
from typing import List, Optional

from .connection import get_conn


def ensure_player(user):
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or username or f"User {user_id}"

    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            "SELECT user_id FROM players WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row:
            conn.execute("""
                UPDATE players
                SET username = ?, full_name = ?, last_played_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (username, full_name, user_id))
        else:
            conn.execute("""
                INSERT INTO players (
                    user_id, username, full_name, last_played_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, username, full_name))


def get_player(user_id: int):
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM players WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def add_points(user_id: int, points: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET total_points = total_points + ?,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (points, user_id))


def record_correct_answer(user_id: int, answer_time: Optional[float] = None):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET correct_answers = correct_answers + 1,
                current_streak = current_streak + 1,
                best_streak = CASE
                    WHEN current_streak + 1 > best_streak THEN current_streak + 1
                    ELSE best_streak
                END,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))

        if answer_time is not None:
            row = conn.execute(
                "SELECT fastest_answer_time FROM players WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if row and (row["fastest_answer_time"] is None or answer_time < row["fastest_answer_time"]):
                conn.execute("""
                    UPDATE players
                    SET fastest_answer_time = ?
                    WHERE user_id = ?
                """, (answer_time, user_id))


def record_wrong_answer(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET wrong_answers = wrong_answers + 1,
                current_streak = 0,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))


def increment_games_played(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET games_played = games_played + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))


def increment_games_won(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET games_won = games_won + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))


def get_top_players(limit: int = 10):
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT *
            FROM players
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
            LIMIT ?
        """, (limit,)).fetchall()


def get_player_rank(user_id: int) -> Optional[int]:
    with closing(get_conn()) as conn:
        rows = conn.execute("""
            SELECT user_id
            FROM players
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
        """).fetchall()

        for i, row in enumerate(rows, start=1):
            if row["user_id"] == user_id:
                return i
        return None


def add_manual_points(user_id: int, points: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET total_points = total_points + ?
            WHERE user_id = ?
        """, (points, user_id))


def get_player_profile(user_id: int):
    player = get_player(user_id)
    rank = get_player_rank(user_id)

    if not player:
        return None, None

    profile_data = (
        player["full_name"],
        player["username"],
        player["total_points"],
        player["games_played"],
        player["correct_answers"],
    )
    return profile_data, rank


def get_global_leaderboard(limit: int = 10):
    rows = get_top_players(limit=limit)
    result = []

    for row in rows:
        result.append((
            row["full_name"],
            row["username"],
            row["total_points"],
        ))

    return result


def get_global_leaderboard_page(limit: int = 15, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT *
            FROM players
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()


def get_player_global_rank_info(user_id: int):
    with closing(get_conn()) as conn:
        me = conn.execute("""
            SELECT total_points, correct_answers, games_won
            FROM players
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if not me:
            return None, 0

        rows = conn.execute("""
            SELECT user_id
            FROM players
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
        """).fetchall()

        for i, row in enumerate(rows, start=1):
            if row["user_id"] == user_id:
                return i, me["total_points"]

        return None, me["total_points"]


def get_all_user_ids():
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT user_id FROM players").fetchall()
        return [row["user_id"] for row in rows]


def get_total_users_count():
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM players").fetchone()
        return row["count"] if row else 0


def get_total_players() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM players").fetchone()
        return row["c"] if row else 0