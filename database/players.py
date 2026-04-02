from contextlib import closing
from typing import Optional, Tuple

from .connection import get_conn


GLOBAL_ORDER_BY = """
ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
"""

PERIOD_ORDER_BY = """
ORDER BY period_points DESC, correct_answers DESC, games_won DESC, p.user_id ASC
"""

DAILY_REWARD_POINTS = 15
WEEK_STREAK_BONUS_POINTS = 50
WEEK_STREAK_STEP = 7


def _normalize_user_input(user_or_id, username: str = None, full_name: str = None):
    if hasattr(user_or_id, "id"):
        return (
            user_or_id.id,
            user_or_id.username if user_or_id.username is not None else username,
            user_or_id.full_name if user_or_id.full_name is not None else full_name,
        )
    return user_or_id, username, full_name


def _get_local_today(conn) -> str:
    row = conn.execute("SELECT DATE('now', 'localtime') AS d").fetchone()
    return row["d"]


def _get_local_yesterday(conn) -> str:
    row = conn.execute("SELECT DATE('now', 'localtime', '-1 day') AS d").fetchone()
    return row["d"]


def _ensure_player_row_in_conn(conn, user_id: int, username: str = None, full_name: str = None):
    conn.execute(
        """
        INSERT OR IGNORE INTO players (user_id, username, full_name)
        VALUES (?, ?, ?)
        """,
        (user_id, username, full_name),
    )

    if username is not None or full_name is not None:
        conn.execute(
            """
            UPDATE players
            SET
                username = COALESCE(?, username),
                full_name = COALESCE(?, full_name)
            WHERE user_id = ?
            """,
            (username, full_name, user_id),
        )


def _ensure_user_row_in_conn(conn, user_id: int, username: str = None, full_name: str = None):
    conn.execute(
        """
        INSERT OR IGNORE INTO users (user_id, username, full_name)
        VALUES (?, ?, ?)
        """,
        (user_id, username, full_name),
    )

    if username is not None or full_name is not None:
        conn.execute(
            """
            UPDATE users
            SET
                username = COALESCE(?, username),
                full_name = COALESCE(?, full_name)
            WHERE user_id = ?
            """,
            (username, full_name, user_id),
        )


def _require_player_updated(result, user_id: int):
    if result.rowcount == 0:
        raise ValueError(f"Player {user_id} does not exist. Use ensure_player first.")


def _fetch_player_rank_and_points(conn, user_id: int) -> Tuple[Optional[int], int]:
    target = conn.execute(
        """
        SELECT total_points, correct_answers, games_won
        FROM players
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    if not target:
        return None, 0

    row = conn.execute(
        """
        SELECT COUNT(*) + 1 AS rank
        FROM players
        WHERE
            COALESCE(total_points, 0) > COALESCE(?, 0)
            OR (
                COALESCE(total_points, 0) = COALESCE(?, 0)
                AND COALESCE(correct_answers, 0) > COALESCE(?, 0)
            )
            OR (
                COALESCE(total_points, 0) = COALESCE(?, 0)
                AND COALESCE(correct_answers, 0) = COALESCE(?, 0)
                AND COALESCE(games_won, 0) > COALESCE(?, 0)
            )
            OR (
                COALESCE(total_points, 0) = COALESCE(?, 0)
                AND COALESCE(correct_answers, 0) = COALESCE(?, 0)
                AND COALESCE(games_won, 0) = COALESCE(?, 0)
                AND user_id < ?
            )
        """,
        (
            target["total_points"], target["total_points"],
            target["correct_answers"], target["total_points"],
            target["correct_answers"], target["games_won"],
            target["total_points"], target["correct_answers"],
            target["games_won"], user_id,
        ),
    ).fetchone()

    return (row["rank"] if row else None, target["total_points"] or 0)


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
        GROUP BY
            p.user_id,
            p.username,
            p.full_name,
            p.correct_answers,
            p.games_won
        {PERIOD_ORDER_BY}
    """


def _get_rank_from_rows(rows, user_id: int, points_key: str):
    for index, row in enumerate(rows, start=1):
        if row["user_id"] == user_id:
            return index, row[points_key]
    return None, 0


def ensure_player(user_or_id, username: str = None, full_name: str = None):
    user_id, username, full_name = _normalize_user_input(user_or_id, username, full_name)

    with closing(get_conn()) as conn, conn:
        _ensure_player_row_in_conn(conn, user_id, username, full_name)


def ensure_user(user_or_id, username: str = None, full_name: str = None):
    user_id, username, full_name = _normalize_user_input(user_or_id, username, full_name)

    with closing(get_conn()) as conn, conn:
        _ensure_user_row_in_conn(conn, user_id, username, full_name)


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


def get_player_stats(user_id: int):
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT
                user_id,
                username,
                full_name,
                total_points,
                games_played,
                games_won,
                duel_games_played,
                duel_games_won,
                correct_answers,
                wrong_answers,
                current_streak,
                best_streak,
                daily_streak,
                best_daily_streak,
                fastest_answer_time,
                last_played_at,
                created_at
            FROM players
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()


def add_points(user_id: int, points: int):
    if points == 0:
        return

    with closing(get_conn()) as conn, conn:
        result = conn.execute(
            """
            UPDATE players
            SET total_points = COALESCE(total_points, 0) + ?,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (points, user_id),
        )
        _require_player_updated(result, user_id)

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
            result = conn.execute(
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
            result = conn.execute(
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

        _require_player_updated(result, user_id)


def record_wrong_answer(user_id: int):
    with closing(get_conn()) as conn, conn:
        result = conn.execute(
            """
            UPDATE players
            SET wrong_answers = COALESCE(wrong_answers, 0) + 1,
                current_streak = 0,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )
        _require_player_updated(result, user_id)


def increment_games_played(user_id: int):
    with closing(get_conn()) as conn, conn:
        result = conn.execute(
            """
            UPDATE players
            SET games_played = COALESCE(games_played, 0) + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )
        _require_player_updated(result, user_id)


def increment_games_won(user_id: int):
    with closing(get_conn()) as conn, conn:
        result = conn.execute(
            """
            UPDATE players
            SET games_won = COALESCE(games_won, 0) + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )
        _require_player_updated(result, user_id)


def increment_duel_games_played(user_id: int):
    with closing(get_conn()) as conn, conn:
        result = conn.execute(
            """
            UPDATE players
            SET duel_games_played = COALESCE(duel_games_played, 0) + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )
        _require_player_updated(result, user_id)


def increment_duel_games_won(user_id: int):
    with closing(get_conn()) as conn, conn:
        result = conn.execute(
            """
            UPDATE players
            SET duel_games_won = COALESCE(duel_games_won, 0) + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )
        _require_player_updated(result, user_id)


def get_top_players(limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            """
            SELECT
                user_id,
                username,
                full_name,
                total_points,
                correct_answers,
                games_won
            FROM players
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()


def get_global_leaderboard(limit: int = 10):
    return get_top_players(limit=limit)


def get_global_leaderboard_page(limit: int = 10, offset: int = 0):
    with closing(get_conn()) as conn:
        return conn.execute(
            f"""
            SELECT
                user_id,
                username,
                full_name,
                total_points,
                correct_answers,
                games_won
            FROM players
            {GLOBAL_ORDER_BY}
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()


def get_player_rank(user_id: int):
    with closing(get_conn()) as conn:
        rank, _ = _fetch_player_rank_and_points(conn, user_id)
        return rank


def get_player_profile(user_id: int):
    with closing(get_conn()) as conn:
        player = conn.execute(
            """
            SELECT
                full_name,
                username,
                total_points,
                games_played,
                games_won,
                duel_games_played,
                duel_games_won,
                correct_answers,
                wrong_answers
            FROM players
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if not player:
            return None, None

        rank, _ = _fetch_player_rank_and_points(conn, user_id)
        return player, rank


def get_player_full_profile(user_id: int):
    with closing(get_conn()) as conn:
        player = conn.execute(
            """
            SELECT
                full_name,
                username,
                total_points,
                games_played,
                games_won,
                duel_games_played,
                duel_games_won,
                correct_answers,
                wrong_answers,
                current_streak,
                best_streak,
                daily_streak,
                best_daily_streak,
                fastest_answer_time,
                last_played_at
            FROM players
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if not player:
            return None, None

        rank, _ = _fetch_player_rank_and_points(conn, user_id)
        return player, rank


def get_player_global_rank_info(user_id: int):
    with closing(get_conn()) as conn:
        return _fetch_player_rank_and_points(conn, user_id)


def recalculate_all_player_wins():
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            UPDATE players
            SET games_won = (
                SELECT COUNT(*)
                FROM games
                WHERE games.winner_user_id = players.user_id
                  AND games.status = 'finished'
            )
            """
        )


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


def get_player_daily_rank_info(user_id: int):
    rows = get_daily_leaderboard_page(limit=100000, offset=0)
    return _get_rank_from_rows(rows, user_id, "period_points")


def get_player_weekly_rank_info(user_id: int):
    rows = get_weekly_leaderboard_page(limit=100000, offset=0)
    return _get_rank_from_rows(rows, user_id, "period_points")


def get_player_monthly_rank_info(user_id: int):
    rows = get_monthly_leaderboard_page(limit=100000, offset=0)
    return _get_rank_from_rows(rows, user_id, "period_points")


def has_claimed_daily_reward(user_id: int):
    with closing(get_conn()) as conn:
        today = _get_local_today(conn)
        row = conn.execute(
            """
            SELECT 1
            FROM daily_reward_claims
            WHERE user_id = ? AND reward_date = ?
            """,
            (user_id, today),
        ).fetchone()
        return bool(row)


def get_daily_reward_status(user_id: int):
    with closing(get_conn()) as conn:
        today = _get_local_today(conn)
        player = conn.execute(
            """
            SELECT daily_streak, best_daily_streak
            FROM players
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        claim = conn.execute(
            """
            SELECT reward_date, base_points, bonus_points, streak_after_claim
            FROM daily_reward_claims
            WHERE user_id = ? AND reward_date = ?
            """,
            (user_id, today),
        ).fetchone()

        daily_streak = (player["daily_streak"] or 0) if player else 0
        best_daily_streak = (player["best_daily_streak"] or 0) if player else 0

        return {
            "claimed_today": bool(claim),
            "today": today,
            "daily_streak": daily_streak,
            "best_daily_streak": best_daily_streak,
            "base_points": claim["base_points"] if claim else 0,
            "bonus_points": claim["bonus_points"] if claim else 0,
            "streak_after_claim": claim["streak_after_claim"] if claim else 0,
            "next_bonus_at": ((daily_streak // WEEK_STREAK_STEP) + 1) * WEEK_STREAK_STEP,
        }


def claim_daily_reward(
    user_id: int,
    base_points: int = DAILY_REWARD_POINTS,
    streak_step: int = WEEK_STREAK_STEP,
    streak_bonus_points: int = WEEK_STREAK_BONUS_POINTS,
):
    with closing(get_conn()) as conn, conn:
        today = _get_local_today(conn)
        yesterday = _get_local_yesterday(conn)

        _ensure_player_row_in_conn(conn, user_id)

        player = conn.execute(
            """
            SELECT daily_streak, best_daily_streak
            FROM players
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        current_daily_streak = (player["daily_streak"] or 0) if player else 0
        best_daily_streak = (player["best_daily_streak"] or 0) if player else 0

        last_claim = conn.execute(
            """
            SELECT reward_date
            FROM daily_reward_claims
            WHERE user_id = ?
            ORDER BY reward_date DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if last_claim and last_claim["reward_date"] == today:
            claim = conn.execute(
                """
                SELECT base_points, bonus_points, streak_after_claim
                FROM daily_reward_claims
                WHERE user_id = ? AND reward_date = ?
                """,
                (user_id, today),
            ).fetchone()

            return {
                "claimed": False,
                "already_claimed": True,
                "reward_date": today,
                "base_points": claim["base_points"],
                "bonus_points": claim["bonus_points"],
                "total_points": claim["base_points"] + claim["bonus_points"],
                "daily_streak": claim["streak_after_claim"],
                "best_daily_streak": best_daily_streak,
            }

        if last_claim and last_claim["reward_date"] == yesterday:
            new_daily_streak = current_daily_streak + 1
        else:
            new_daily_streak = 1

        new_best_daily_streak = max(best_daily_streak, new_daily_streak)
        bonus_points = streak_bonus_points if new_daily_streak % streak_step == 0 else 0
        total_points = base_points + bonus_points

        try:
            conn.execute(
                """
                INSERT INTO daily_reward_claims (
                    user_id,
                    reward_date,
                    base_points,
                    bonus_points,
                    streak_after_claim
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, today, base_points, bonus_points, new_daily_streak),
            )
        except Exception:
            claim = conn.execute(
                """
                SELECT base_points, bonus_points, streak_after_claim
                FROM daily_reward_claims
                WHERE user_id = ? AND reward_date = ?
                """,
                (user_id, today),
            ).fetchone()

            return {
                "claimed": False,
                "already_claimed": True,
                "reward_date": today,
                "base_points": claim["base_points"],
                "bonus_points": claim["bonus_points"],
                "total_points": claim["base_points"] + claim["bonus_points"],
                "daily_streak": claim["streak_after_claim"],
                "best_daily_streak": best_daily_streak,
            }

        result = conn.execute(
            """
            UPDATE players
            SET total_points = COALESCE(total_points, 0) + ?,
                daily_streak = ?,
                best_daily_streak = ?,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (total_points, new_daily_streak, new_best_daily_streak, user_id),
        )
        _require_player_updated(result, user_id)

        conn.execute(
            """
            INSERT INTO player_points_history (user_id, points)
            VALUES (?, ?)
            """,
            (user_id, total_points),
        )

        return {
            "claimed": True,
            "already_claimed": False,
            "reward_date": today,
            "base_points": base_points,
            "bonus_points": bonus_points,
            "total_points": total_points,
            "daily_streak": new_daily_streak,
            "best_daily_streak": new_best_daily_streak,
        }


def reset_daily_streak_if_missed(user_id: int):
    with closing(get_conn()) as conn, conn:
        yesterday = _get_local_yesterday(conn)

        last_claim = conn.execute(
            """
            SELECT reward_date
            FROM daily_reward_claims
            WHERE user_id = ?
            ORDER BY reward_date DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if not last_claim or last_claim["reward_date"] != yesterday:
            conn.execute(
                """
                UPDATE players
                SET daily_streak = 0
                WHERE user_id = ?
                """,
                (user_id,),
            )
            return True

        return False


def get_player_streak_info(user_id: int):
    with closing(get_conn()) as conn:
        row = conn.execute(
            """
            SELECT
                current_streak,
                best_streak,
                daily_streak,
                best_daily_streak
            FROM players
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if not row:
            return {
                "current_streak": 0,
                "best_streak": 0,
                "daily_streak": 0,
                "best_daily_streak": 0,
            }

        return {
            "current_streak": row["current_streak"] or 0,
            "best_streak": row["best_streak"] or 0,
            "daily_streak": row["daily_streak"] or 0,
            "best_daily_streak": row["best_daily_streak"] or 0,
        }


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
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM players
            WHERE
                COALESCE(games_played, 0) > 0
                OR COALESCE(correct_answers, 0) > 0
                OR COALESCE(wrong_answers, 0) > 0
                OR COALESCE(total_points, 0) > 0
                OR COALESCE(games_won, 0) > 0
                OR COALESCE(duel_games_played, 0) > 0
                OR COALESCE(duel_games_won, 0) > 0
            """
        ).fetchone()
    return row["count"] if row else 0


def get_total_users_count():
    with closing(get_conn()) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            """
        ).fetchone()
    return row["count"] if row else 0