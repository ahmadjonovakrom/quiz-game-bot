import random
from contextlib import closing
from typing import List, Optional

from .connection import get_conn


GROUP_ORDER_BY = """
ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
"""

GROUP_PERIOD_ORDER_BY = """
ORDER BY period_points DESC, gs.correct_answers DESC, gs.games_won DESC, gs.user_id ASC
"""


def _user_identity(user):
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or username or f"User {user_id}"
    return user_id, username, full_name


def ensure_chat(chat) -> None:
    chat_id = chat.id
    chat_type = chat.type
    title = getattr(chat, "title", None) or ""
    username = getattr(chat, "username", None) or ""

    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            "SELECT chat_id FROM chats WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()

        if row:
            conn.execute(
                """
                UPDATE chats
                SET chat_type = ?,
                    title = ?,
                    username = ?,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE chat_id = ?
                """,
                (chat_type, title, username, chat_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO chats (
                    chat_id, chat_type, title, username, is_active, updated_at
                ) VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """,
                (chat_id, chat_type, title, username),
            )


def deactivate_chat(chat_id: int) -> None:
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            UPDATE chats
            SET is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE chat_id = ?
            """,
            (chat_id,),
        )


def get_all_chat_ids(include_users: bool = True, include_groups: bool = True) -> List[int]:
    ids = set()

    with closing(get_conn()) as conn:
        if include_users:
            player_rows = conn.execute(
                """
                SELECT user_id
                FROM players
                """
            ).fetchall()
            for row in player_rows:
                ids.add(row["user_id"])

        if include_groups:
            chat_rows = conn.execute(
                """
                SELECT chat_id
                FROM chats
                WHERE is_active = 1
                  AND chat_type IN ('group', 'supergroup')
                """
            ).fetchall()
            for row in chat_rows:
                ids.add(row["chat_id"])

    return list(ids)


def ensure_group_player(chat_id: int, user) -> None:
    user_id, username, full_name = _user_identity(user)

    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, last_played_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_played_at = CURRENT_TIMESTAMP
            """,
            (chat_id, user_id, username, full_name),
        )


def add_group_points(chat_id: int, user, points: int):
    user_id, username, full_name = _user_identity(user)

    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, total_points, last_played_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                total_points = group_scores.total_points + excluded.total_points,
                last_played_at = CURRENT_TIMESTAMP
            """,
            (chat_id, user_id, username, full_name, points),
        )

        conn.execute(
            """
            INSERT INTO group_points_history (chat_id, user_id, points)
            VALUES (?, ?, ?)
            """,
            (chat_id, user_id, points),
        )


def record_group_correct_answer(chat_id: int, user):
    user_id, username, full_name = _user_identity(user)

    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, correct_answers, last_played_at
            )
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                correct_answers = group_scores.correct_answers + 1,
                last_played_at = CURRENT_TIMESTAMP
            """,
            (chat_id, user_id, username, full_name),
        )


def record_group_wrong_answer(chat_id: int, user) -> None:
    user_id, username, full_name = _user_identity(user)

    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, wrong_answers, last_played_at
            )
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                wrong_answers = group_scores.wrong_answers + 1,
                last_played_at = CURRENT_TIMESTAMP
            """,
            (chat_id, user_id, username, full_name),
        )


def increment_group_games_played(chat_id: int, user):
    user_id, username, full_name = _user_identity(user)

    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, games_played, last_played_at
            )
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                games_played = group_scores.games_played + 1,
                last_played_at = CURRENT_TIMESTAMP
            """,
            (chat_id, user_id, username, full_name),
        )


def increment_group_games_won(chat_id: int, user):
    user_id, username, full_name = _user_identity(user)

    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, games_won, last_played_at
            )
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                games_won = group_scores.games_won + 1,
                last_played_at = CURRENT_TIMESTAMP
            """,
            (chat_id, user_id, username, full_name),
        )


def get_group_leaderboard(chat_id: int, limit: int = 10):
    return get_group_leaderboard_page(chat_id=chat_id, limit=limit, offset=0)


def get_group_leaderboard_page(chat_id: int, limit: int = 15, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            f"""
            SELECT
                chat_id,
                user_id,
                username,
                full_name,
                total_points,
                correct_answers,
                wrong_answers,
                games_played,
                games_won,
                last_played_at
            FROM group_scores
            WHERE chat_id = ?
            {GROUP_ORDER_BY}
            LIMIT ? OFFSET ?
            """,
            (chat_id, limit, offset),
        ).fetchall()


def _group_period_sql(where_clause: str) -> str:
    return f"""
        SELECT
            gs.chat_id,
            gs.user_id,
            gs.username,
            gs.full_name,
            COALESCE(SUM(gph.points), 0) AS period_points,
            gs.correct_answers,
            gs.games_won
        FROM group_scores gs
        LEFT JOIN group_points_history gph
          ON gs.chat_id = gph.chat_id
         AND gs.user_id = gph.user_id
         AND {where_clause}
        WHERE gs.chat_id = ?
        GROUP BY
            gs.chat_id,
            gs.user_id,
            gs.username,
            gs.full_name,
            gs.correct_answers,
            gs.games_won
        HAVING period_points > 0
        {GROUP_PERIOD_ORDER_BY}
    """


def get_group_daily_leaderboard(chat_id: int, limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            _group_period_sql("DATE(gph.created_at, 'localtime') = DATE('now', 'localtime')")
            + "\nLIMIT ? OFFSET ?",
            (chat_id, limit, offset),
        ).fetchall()


def get_group_weekly_leaderboard(chat_id: int, limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            _group_period_sql(
                "DATE(gph.created_at, 'localtime') >= DATE('now', 'localtime', 'weekday 1', '-7 days') "
                "AND DATE(gph.created_at, 'localtime') <= DATE('now', 'localtime')"
            )
            + "\nLIMIT ? OFFSET ?",
            (chat_id, limit, offset),
        ).fetchall()


def get_group_monthly_leaderboard(chat_id: int, limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            _group_period_sql(
                "strftime('%Y-%m', gph.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')"
            )
            + "\nLIMIT ? OFFSET ?",
            (chat_id, limit, offset),
        ).fetchall()


def get_player_group_rank_info(chat_id: int, user_id: int):
    with closing(get_conn()) as conn:
        me = conn.execute(
            """
            SELECT total_points, correct_answers, games_won
            FROM group_scores
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        ).fetchone()

        if not me:
            return None, 0

        rows = conn.execute(
            f"""
            SELECT user_id
            FROM group_scores
            WHERE chat_id = ?
            {GROUP_ORDER_BY}
            """,
            (chat_id,),
        ).fetchall()

    for index, row in enumerate(rows, start=1):
        if row["user_id"] == user_id:
            return index, me["total_points"]

    return None, me["total_points"]


def _get_group_period_rank_info(chat_id: int, user_id: int, where_clause: str):
    with closing(get_conn()) as conn:
        me = conn.execute(
            f"""
            SELECT
                gs.user_id,
                COALESCE(SUM(gph.points), 0) AS period_points
            FROM group_scores gs
            LEFT JOIN group_points_history gph
              ON gs.chat_id = gph.chat_id
             AND gs.user_id = gph.user_id
             AND {where_clause}
            WHERE gs.chat_id = ?
              AND gs.user_id = ?
            GROUP BY gs.user_id
            HAVING period_points > 0
            """,
            (chat_id, user_id),
        ).fetchone()

        if not me:
            return None, 0

        rows = conn.execute(
            f"""
            SELECT
                gs.user_id,
                COALESCE(SUM(gph.points), 0) AS period_points,
                gs.correct_answers,
                gs.games_won
            FROM group_scores gs
            LEFT JOIN group_points_history gph
              ON gs.chat_id = gph.chat_id
             AND gs.user_id = gph.user_id
             AND {where_clause}
            WHERE gs.chat_id = ?
            GROUP BY
                gs.user_id,
                gs.correct_answers,
                gs.games_won
            HAVING period_points > 0
            ORDER BY
                period_points DESC,
                gs.correct_answers DESC,
                gs.games_won DESC,
                gs.user_id ASC
            """,
            (chat_id,),
        ).fetchall()

    for index, row in enumerate(rows, start=1):
        if row["user_id"] == user_id:
            return index, me["period_points"]

    return None, me["period_points"]


def get_player_group_daily_rank_info(chat_id: int, user_id: int):
    return _get_group_period_rank_info(
        chat_id,
        user_id,
        "DATE(gph.created_at, 'localtime') = DATE('now', 'localtime')",
    )


def get_player_group_weekly_rank_info(chat_id: int, user_id: int):
    return _get_group_period_rank_info(
        chat_id,
        user_id,
        "DATE(gph.created_at, 'localtime') >= DATE('now', 'localtime', 'weekday 1', '-7 days') "
        "AND DATE(gph.created_at, 'localtime') <= DATE('now', 'localtime')",
    )


def get_player_group_monthly_rank_info(chat_id: int, user_id: int):
    return _get_group_period_rank_info(
        chat_id,
        user_id,
        "strftime('%Y-%m', gph.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')",
    )


def create_game(chat_id: int, total_players: int = 0, total_rounds: int = 0, status: str = "running") -> int:
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            """
            INSERT INTO games (chat_id, total_players, total_rounds, status)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, total_players, total_rounds, status),
        )
        return cur.lastrowid


def finish_game(
    game_id: int,
    winner_user_id: Optional[int],
    total_players: int,
    total_rounds: int,
    status: str = "finished",
):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            UPDATE games
            SET ended_at = CURRENT_TIMESTAMP,
                winner_user_id = ?,
                total_players = ?,
                total_rounds = ?,
                status = ?
            WHERE id = ?
            """,
            (winner_user_id, total_players, total_rounds, status, game_id),
        )


def record_game_result(
    game_id: int,
    user_id: int,
    score: int,
    correct_count: int = 0,
    wrong_count: int = 0,
    avg_answer_time: Optional[float] = None,
    position: Optional[int] = None,
):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT INTO game_results (
                game_id, user_id, score, correct_count, wrong_count, avg_answer_time, position
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (game_id, user_id, score, correct_count, wrong_count, avg_answer_time, position),
        )


def get_total_games() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM games").fetchone()
    return row["c"] if row else 0


def get_total_groups() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM chats
            WHERE is_active = 1
              AND chat_type IN ('group', 'supergroup')
            """
        ).fetchone()
    return row["c"] if row else 0


def get_broadcast_chat_ids() -> List[int]:
    return get_all_chat_ids(include_users=True, include_groups=True)


def has_played_daily_quiz(user_id: int, quiz_date: str) -> bool:
    with closing(get_conn()) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM daily_quiz_attempts
            WHERE user_id = ? AND quiz_date = ?
            """,
            (user_id, quiz_date),
        ).fetchone()
    return row is not None


def record_daily_quiz_attempt(user_id: int, quiz_date: str):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO daily_quiz_attempts (user_id, quiz_date)
            VALUES (?, ?)
            """,
            (user_id, quiz_date),
        )
        
def get_group_tag_candidates(chat_id: int, limit: int = 30):
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT
                user_id,
                username,
                full_name,
                last_played_at
            FROM group_scores
            WHERE chat_id = ?
            ORDER BY
                CASE WHEN last_played_at IS NULL THEN 1 ELSE 0 END,
                last_played_at DESC,
                user_id ASC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()


def pick_random_group_tag_candidates(chat_id: int, limit: int = 30):
    rows = get_group_tag_candidates(chat_id, limit=limit)

    # 🔥 fallback if empty
    if not rows:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT user_id, username, full_name
                FROM players
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    rows = list(rows)
    random.shuffle(rows)
    return rows