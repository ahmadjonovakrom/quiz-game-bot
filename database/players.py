from contextlib import closing

from .connection import get_conn


def ensure_player(user_id: int, username: str = None, full_name: str = None):
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
            INSERT INTO players (
                user_id,
                username,
                full_name
            )
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


def get_top_players(limit: int = 10):
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT
                user_id,
                username,
                full_name,
                total_points,
                correct_answers,
                games_won
            FROM players
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
            LIMIT ?
        """, (limit,)).fetchall()


def get_player_profile(user_id: int):
    with closing(get_conn()) as conn:
        player = conn.execute("""
            SELECT
                full_name,
                username,
                total_points,
                games_played,
                correct_answers
            FROM players
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if not player:
            return None, None

        rank_row = conn.execute("""
            SELECT COUNT(*) + 1 AS rank
            FROM players
            WHERE total_points > (
                SELECT total_points
                FROM players
                WHERE user_id = ?
            )
        """, (user_id,)).fetchone()

        rank = rank_row["rank"] if rank_row else None
        return player, rank


def get_player_global_rank_info(user_id: int):
    with closing(get_conn()) as conn:
        me = conn.execute("""
            SELECT user_id, total_points
            FROM players
            WHERE user_id = ?
        """, (user_id,)).fetchone()

        if not me:
            return None, 0

        rows = conn.execute("""
            SELECT user_id, total_points
            FROM players
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
        """).fetchall()

        for index, row in enumerate(rows, start=1):
            if row["user_id"] == user_id:
                return index, row["total_points"]

        return None, 0


def get_daily_leaderboard_page(limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT
                p.user_id,
                p.username,
                p.full_name,
                COALESCE(SUM(h.points), 0) AS period_points
            FROM players p
            JOIN player_points_history h
                ON p.user_id = h.user_id
            WHERE DATE(h.created_at, 'localtime') = DATE('now', 'localtime')
            GROUP BY p.user_id, p.username, p.full_name
            ORDER BY period_points DESC, p.correct_answers DESC, p.games_won DESC, p.user_id ASC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()


def get_weekly_leaderboard_page(limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT
                p.user_id,
                p.username,
                p.full_name,
                COALESCE(SUM(h.points), 0) AS period_points
            FROM players p
            JOIN player_points_history h
                ON p.user_id = h.user_id
            WHERE DATE(h.created_at, 'localtime') >= DATE('now', 'localtime', '-6 days')
            GROUP BY p.user_id, p.username, p.full_name
            ORDER BY period_points DESC, p.correct_answers DESC, p.games_won DESC, p.user_id ASC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()


def get_monthly_leaderboard_page(limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT
                p.user_id,
                p.username,
                p.full_name,
                COALESCE(SUM(h.points), 0) AS period_points
            FROM players p
            JOIN player_points_history h
                ON p.user_id = h.user_id
            WHERE strftime('%Y-%m', h.created_at, 'localtime') = strftime('%Y-%m', 'now', 'localtime')
            GROUP BY p.user_id, p.username, p.full_name
            ORDER BY period_points DESC, p.correct_answers DESC, p.games_won DESC, p.user_id ASC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()


def increment_games_played(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET games_played = COALESCE(games_played, 0) + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))


def increment_games_won(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET games_won = COALESCE(games_won, 0) + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))


def record_correct_answer(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
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
        """, (user_id,))


def record_wrong_answer(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET wrong_answers = COALESCE(wrong_answers, 0) + 1,
                current_streak = 0,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))


def get_total_players():
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM players").fetchone()
        return row["count"] if row else 0


def get_total_users_count():
    return get_total_players()