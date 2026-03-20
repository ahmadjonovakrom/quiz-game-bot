from contextlib import closing

from .connection import get_conn


GLOBAL_ORDER_BY = """
ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
"""

PERIOD_ORDER_BY = """
ORDER BY period_points DESC, correct_answers DESC, games_won DESC, user_id ASC
"""


def _normalize_user_input(user_or_id, username=None, full_name=None):
    if hasattr(user_or_id, "id"):
        return user_or_id.id, user_or_id.username, user_or_id.full_name
    return user_or_id, username, full_name


def ensure_player(user_or_id, username: str = None, full_name: str = None):
    user_id, username, full_name = _normalize_user_input(user_or_id, username, full_name)

    with closing(get_conn()) as conn, conn:
        existing = conn.execute(
            "SELECT user_id FROM players WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE players
                SET username = ?, full_name = ?
                WHERE user_id = ?
                """,
                (username, full_name, user_id),
            )
            return

        conn.execute(
            """
            INSERT INTO players (
                user_id,
                username,
                full_name
            ) VALUES (?, ?, ?)
            """,
            (user_id, username, full_name),
        )


def get_player(user_id: int):
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT *
            FROM players
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()


def add_points(user_id: int, points: int):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            UPDATE players
            SET total_points = COALESCE(total_points, 0) + ?,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (points, user_id),
        )

        conn.execute(
            """
            INSERT INTO player_points_history (user_id, points)
            VALUES (?, ?)
            """,
            (user_id, points),
        )


def add_manual_points(user_id: int, points: int):
    add_points(user_id, points)


def record_correct_answer(user_id: int, answer_time=None):
    with closing(get_conn()) as conn, conn:
        if answer_time is None:
            conn.execute(
                """
                UPDATE players
                SET correct_answers = COALESCE(correct_answers, 0) + 1,
                    current_streak = COALESCE(current_streak, 0) + 1,
                    best_streak = CASE
                        WHEN COALESCE(current_streak, 0) + 1 > COALESCE(best_streak, 0)
                        THEN COALESCE(current_streak, 0) + 1
                        ELSE COALESCE(best_streak, 0)
                    END,
                    last_played_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,),
            )
        else:
            conn.execute(
                """
                UPDATE players
                SET correct_answers = COALESCE(correct_answers, 0) + 1,
                    current_streak = COALESCE(current_streak, 0) + 1,
                    best_streak = CASE
                        WHEN COALESCE(current_streak, 0) + 1 > COALESCE(best_streak, 0)
                        THEN COALESCE(current_streak, 0) + 1
                        ELSE COALESCE(best_streak, 0)
                    END,
                    fastest_answer_time = CASE
                        WHEN fastest_answer_time IS NULL OR ? < fastest_answer_time
                        THEN ?
                        ELSE fastest_answer_time
                    END,
                    last_played_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (answer_time, answer_time, user_id),
            )


def record_wrong_answer(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            UPDATE players
            SET wrong_answers = COALESCE(wrong_answers, 0) + 1,
                current_streak = 0,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )


def increment_games_played(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            UPDATE players
            SET games_played = COALESCE(games_played, 0) + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )


def increment_games_won(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            UPDATE players
            SET games_won = COALESCE(games_won, 0) + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )


def get_top_players(limit: int = 10):
    with closing(get_conn()) as conn:
        return conn.execute(
            f"""
            SELECT user_id, username, full_name, total_points, correct_answers, games_won
            FROM players
            {GLOBAL_ORDER_BY}
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_global_leaderboard(limit: int = 10):
    return get_top_players(limit=limit)


def get_global_leaderboard_page(limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            f"""
            SELECT user_id, username, full_name, total_points, correct_answers, games_won
            FROM players
            {GLOBAL_ORDER_BY}
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()


def get_player_rank(user_id: int):
    with closing(get_conn()) as conn:
        rows = conn.execute(
            f"""
            SELECT user_id
            FROM players
            {GLOBAL_ORDER_BY}
            """
        ).fetchall()

    for index, row in enumerate(rows, start=1):
        if row["user_id"] == user_id:
            return index
    return None


def get_player_profile(user_id: int):
    with closing(get_conn()) as conn:
        player = conn.execute(
            """
            SELECT full_name, username, total_points, games_played, correct_answers
            FROM players
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if not player:
        return None, None

    rank = get_player_rank(user_id)
    return player, rank


def get_player_global_rank_info(user_id: int):
    with closing(get_conn()) as conn:
        rows = conn.execute(
            f"""
            SELECT user_id, total_points
            FROM players
            {GLOBAL_ORDER_BY}
            """
        ).fetchall()

    for index, row in enumerate(rows, start=1):
        if row["user_id"] == user_id:
            return index, row["total_points"]
    return None, 0


def _period_rows_sql(where_clause: str):
    return f"""
        SELECT
            p.user_id,
            p.username,
            p.full_name,
            COALESCE(SUM(h.points), 0) AS period_points,
            p.correct_answers,
            p.games_won
        FROM players p
        JOIN player_points_history h ON p.user_id = h.user_id
        WHERE {where_clause}
        GROUP BY p.user_id, p.username, p.full_name, p.correct_answers, p.games_won
        {PERIOD_ORDER_BY}
    """


def get_daily_leaderboard_page(limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            _period_rows_sql("DATE(h.created_at, 'localtime') = DATE('now', 'localtime')")
            + "\nLIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def get_weekly_leaderboard_page(limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            _period_rows_sql(
                "DATE(h.created_at, 'localtime') >= DATE('now', 'localtime', 'weekday 1', '-7 days') "
                "AND DATE(h.created_at, 'localtime') <= DATE('now', 'localtime')"
            )
            + "\nLIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def get_monthly_leaderboard_page(limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            _period_rows_sql(
                "strftime('%Y-%m', h.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')"
            )
            + "\nLIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def _get_rank_from_rows(rows, user_id: int, points_key: str):
    for index, row in enumerate(rows, start=1):
        if row["user_id"] == user_id:
            return index, row[points_key]
    return None, 0


def get_player_daily_rank_info(user_id: int):
    rows = get_daily_leaderboard_page(limit=100000, offset=0)
    return _get_rank_from_rows(rows, user_id, "period_points")


def get_player_weekly_rank_info(user_id: int):
    rows = get_weekly_leaderboard_page(limit=100000, offset=0)
    return _get_rank_from_rows(rows, user_id, "period_points")


def get_player_monthly_rank_info(user_id: int):
    rows = get_monthly_leaderboard_page(limit=100000, offset=0)
    return _get_rank_from_rows(rows, user_id, "period_points")


def get_all_user_ids():
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT user_id
            FROM players
            """
        ).fetchall()
    return [row["user_id"] for row in rows]


def get_total_players():
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM players").fetchone()
    return row["count"] if row else 0


def get_total_users_count():
    return get_total_players()