from contextlib import closing
from .connection import get_conn


# ================= COMMON ORDER =================

GLOBAL_ORDER_BY = """
ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
"""

PERIOD_ORDER_BY = """
ORDER BY period_points DESC, correct_answers DESC, games_won DESC, user_id ASC
"""


# ================= HELPERS =================

def _normalize_user_input(user_or_id, username=None, full_name=None):
    if hasattr(user_or_id, "id"):
        return user_or_id.id, user_or_id.username, user_or_id.full_name
    return user_or_id, username, full_name


# ================= PLAYER =================

def ensure_player(user_or_id, username: str = None, full_name: str = None):
    user_id, username, full_name = _normalize_user_input(user_or_id, username, full_name)

    with closing(get_conn()) as conn, conn:
        existing = conn.execute(
            "SELECT user_id FROM players WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE players
                SET username = ?, full_name = ?
                WHERE user_id = ?
            """, (username, full_name, user_id))
            return

        conn.execute("""
            INSERT INTO players (user_id, username, full_name)
            VALUES (?, ?, ?)
        """, (user_id, username, full_name))


def add_points(user_id: int, points: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET total_points = COALESCE(total_points, 0) + ?,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (points, user_id))

        conn.execute("""
            INSERT INTO player_points_history (user_id, points)
            VALUES (?, ?)
        """, (user_id, points))


# ================= STATS =================

def record_correct_answer(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET correct_answers = COALESCE(correct_answers, 0) + 1,
                current_streak = COALESCE(current_streak, 0) + 1,
                best_streak = CASE
                    WHEN COALESCE(current_streak, 0) + 1 > COALESCE(best_streak, 0)
                    THEN COALESCE(current_streak, 0) + 1
                    ELSE best_streak
                END
            WHERE user_id = ?
        """, (user_id,))


def record_wrong_answer(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET wrong_answers = COALESCE(wrong_answers, 0) + 1,
                current_streak = 0
            WHERE user_id = ?
        """, (user_id,))


def increment_games_played(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET games_played = COALESCE(games_played, 0) + 1
            WHERE user_id = ?
        """, (user_id,))


def increment_games_won(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET games_won = COALESCE(games_won, 0) + 1
            WHERE user_id = ?
        """, (user_id,))


# ================= LEADERBOARDS =================

def get_top_players(limit: int = 10):
    with closing(get_conn()) as conn:
        return conn.execute(f"""
            SELECT user_id, username, full_name, total_points, correct_answers, games_won
            FROM players
            {GLOBAL_ORDER_BY}
            LIMIT ?
        """, (limit,)).fetchall()


def get_player_profile(user_id: int):
    with closing(get_conn()) as conn:
        player = conn.execute("""
            SELECT full_name, username, total_points, games_played, correct_answers
            FROM players
            WHERE user_id = ?
        """, (user_id,)).fetchone()

    if not player:
        return None, None

    rank = get_player_rank(user_id)
    return player, rank


def get_player_rank(user_id: int):
    with closing(get_conn()) as conn:
        rows = conn.execute(f"""
            SELECT user_id
            FROM players
            {GLOBAL_ORDER_BY}
        """).fetchall()

    for i, row in enumerate(rows, start=1):
        if row["user_id"] == user_id:
            return i
    return None


def get_player_global_rank_info(user_id: int):
    with closing(get_conn()) as conn:
        rows = conn.execute(f"""
            SELECT user_id, total_points
            FROM players
            {GLOBAL_ORDER_BY}
        """).fetchall()

    for i, row in enumerate(rows, start=1):
        if row["user_id"] == user_id:
            return i, row["total_points"]
    return None, 0


# ================= PERIOD LEADERBOARDS =================

def _period_sql(where):
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
        WHERE {where}
        GROUP BY p.user_id
        {PERIOD_ORDER_BY}
    """


def get_daily_leaderboard_page(limit=10, offset=0):
    with closing(get_conn()) as conn:
        return conn.execute(
            _period_sql("DATE(h.created_at) = DATE('now')") + " LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def get_weekly_leaderboard_page(limit=10, offset=0):
    with closing(get_conn()) as conn:
        return conn.execute(
            _period_sql("DATE(h.created_at) >= DATE('now','-7 days')") + " LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def get_monthly_leaderboard_page(limit=10, offset=0):
    with closing(get_conn()) as conn:
        return conn.execute(
            _period_sql("strftime('%Y-%m', h.created_at) = strftime('%Y-%m','now')")
            + " LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


# ================= TOTAL =================

def get_total_users_count():
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM players").fetchone()
    return row["c"] if row else 0