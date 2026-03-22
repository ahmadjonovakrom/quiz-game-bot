from contextlib import closing

from .connection import get_conn


def get_setting(key: str, default=None):
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))


def get_all_settings():
    with closing(get_conn()) as conn:
        rows = conn.execute("""
            SELECT key, value
            FROM settings
            ORDER BY key
        """).fetchall()
    return {row["key"]: row["value"] for row in rows}


def get_game_settings():
    settings = get_all_settings()
    return {
        "min_players": int(settings.get("min_players", 1)),
        "join_seconds": int(settings.get("join_seconds", 60)),
        "question_seconds": int(settings.get("question_seconds", 15)),
        "speed_bonus_seconds": int(settings.get("speed_bonus_seconds", 5)),
        "speed_bonus_points": int(settings.get("speed_bonus_points", 5)),
        "points": {
            "easy": int(settings.get("points_easy", 15)),
            "medium": int(settings.get("points_medium", 25)),
            "hard": int(settings.get("points_hard", 35)),
        },
    }