import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional, List

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "quizbot.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                total_points INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                wrong_answers INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                fastest_answer_time REAL,
                last_played_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option INTEGER NOT NULL,
                category TEXT DEFAULT 'mixed',
                difficulty TEXT DEFAULT 'easy',
                created_by INTEGER,
                is_active INTEGER DEFAULT 1,
                times_used INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                ended_at TEXT,
                winner_user_id INTEGER,
                total_players INTEGER DEFAULT 0,
                total_rounds INTEGER DEFAULT 0,
                status TEXT DEFAULT 'finished'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                score INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                avg_answer_time REAL,
                position INTEGER,
                FOREIGN KEY (game_id) REFERENCES games(id),
                FOREIGN KEY (user_id) REFERENCES players(user_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS group_scores (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                total_points INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                last_played_at TEXT,
                PRIMARY KEY (chat_id, user_id)
            )
        """)


# -------------------------
# Helpers
# -------------------------

def normalize_correct_option(value) -> int:
    if isinstance(value, int):
        if value in (1, 2, 3, 4):
            return value
        raise ValueError("correct_option must be 1, 2, 3, or 4")

    if isinstance(value, str):
        value = value.strip().upper()
        mapping = {"A": 1, "B": 2, "C": 3, "D": 4}
        if value in mapping:
            return mapping[value]
        if value.isdigit() and int(value) in (1, 2, 3, 4):
            return int(value)

    raise ValueError("correct_option must be A/B/C/D or 1/2/3/4")


def correct_option_to_letter(value: int) -> str:
    mapping = {1: "A", 2: "B", 3: "C", 4: "D"}
    return mapping.get(value, "?")


# -------------------------
# Player functions
# -------------------------

def ensure_player(user):
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or username or f"User {user_id}"

    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            "SELECT user_id FROM players WHERE user_id = ?",
            (user_id,)
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


def get_player(user_id: int) -> Optional[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM players WHERE user_id = ?",
            (user_id,)
        ).fetchone()


def add_points(user_id: int, points: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET total_points = total_points + ?,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (points, user_id))


def add_group_points(chat_id: int, user, points: int):
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or username or f"User {user_id}"

    with closing(get_conn()) as conn, conn:
        conn.execute("""
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, total_points, last_played_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                total_points = group_scores.total_points + excluded.total_points,
                last_played_at = CURRENT_TIMESTAMP
        """, (chat_id, user_id, username, full_name, points))


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
                (user_id,)
            ).fetchone()

            if row and (row["fastest_answer_time"] is None or answer_time < row["fastest_answer_time"]):
                conn.execute("""
                    UPDATE players
                    SET fastest_answer_time = ?
                    WHERE user_id = ?
                """, (answer_time, user_id))


def record_group_correct_answer(chat_id: int, user):
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or username or f"User {user_id}"

    with closing(get_conn()) as conn, conn:
        conn.execute("""
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, correct_answers, last_played_at
            )
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                correct_answers = group_scores.correct_answers + 1,
                last_played_at = CURRENT_TIMESTAMP
        """, (chat_id, user_id, username, full_name))


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


def increment_group_games_played(chat_id: int, user):
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or username or f"User {user_id}"

    with closing(get_conn()) as conn, conn:
        conn.execute("""
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, games_played, last_played_at
            )
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                games_played = group_scores.games_played + 1,
                last_played_at = CURRENT_TIMESTAMP
        """, (chat_id, user_id, username, full_name))


def increment_games_won(user_id: int):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE players
            SET games_won = games_won + 1,
                last_played_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))


def increment_group_games_won(chat_id: int, user):
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or username or f"User {user_id}"

    with closing(get_conn()) as conn, conn:
        conn.execute("""
            INSERT INTO group_scores (
                chat_id, user_id, username, full_name, games_won, last_played_at
            )
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                games_won = group_scores.games_won + 1,
                last_played_at = CURRENT_TIMESTAMP
        """, (chat_id, user_id, username, full_name))


def get_top_players(limit: int = 10) -> List[sqlite3.Row]:
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


def get_group_leaderboard(chat_id: int, limit: int = 10):
    rows = get_group_leaderboard_page(chat_id=chat_id, limit=limit, offset=0)
    result = []

    for row in rows:
        result.append((
            row["full_name"],
            row["username"],
            row["total_points"],
        ))

    return result


def get_global_leaderboard_page(limit: int = 15, offset: int = 0) -> List[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT *
            FROM players
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()


def get_group_leaderboard_page(chat_id: int, limit: int = 15, offset: int = 0) -> List[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT *
            FROM group_scores
            WHERE chat_id = ?
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
            LIMIT ? OFFSET ?
        """, (chat_id, limit, offset)).fetchall()


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


def get_player_group_rank_info(chat_id: int, user_id: int):
    with closing(get_conn()) as conn:
        me = conn.execute("""
            SELECT total_points, correct_answers, games_won
            FROM group_scores
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id)).fetchone()

        if not me:
            return None, 0

        rows = conn.execute("""
            SELECT user_id
            FROM group_scores
            WHERE chat_id = ?
            ORDER BY total_points DESC, correct_answers DESC, games_won DESC, user_id ASC
        """, (chat_id,)).fetchall()

        for i, row in enumerate(rows, start=1):
            if row["user_id"] == user_id:
                return i, me["total_points"]

        return None, me["total_points"]


# -------------------------
# Question functions
# -------------------------

def add_question(
    question_text: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    correct_option,
    category: str = "mixed",
    difficulty: str = "easy",
    created_by: Optional[int] = None,
):
    correct_option = normalize_correct_option(correct_option)

    with closing(get_conn()) as conn, conn:
        conn.execute("""
            INSERT INTO questions (
                question_text, option_a, option_b, option_c, option_d,
                correct_option, category, difficulty, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            question_text.strip(),
            option_a.strip(),
            option_b.strip(),
            option_c.strip(),
            option_d.strip(),
            correct_option,
            category.strip().lower(),
            difficulty.strip().lower(),
            created_by,
        ))


def get_random_question(category: Optional[str] = None, difficulty: Optional[str] = None):
    query = """
        SELECT *
        FROM questions
        WHERE is_active = 1
    """
    params = []

    if category:
        query += " AND category = ?"
        params.append(category.strip().lower())

    if difficulty:
        query += " AND difficulty = ?"
        params.append(difficulty.strip().lower())

    query += " ORDER BY RANDOM() LIMIT 1"

    with closing(get_conn()) as conn, conn:
        row = conn.execute(query, params).fetchone()

        if row:
            conn.execute("""
                UPDATE questions
                SET times_used = times_used + 1
                WHERE id = ?
            """, (row["id"],))

        return row


def list_questions(limit: int = 20) -> List[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT *
            FROM questions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()


def get_all_questions(limit: int = 50) -> List[tuple]:
    rows = list_questions(limit)
    result = []

    for row in rows:
        result.append((
            row["id"],
            row["question_text"],
            row["option_a"],
            row["option_b"],
            row["option_c"],
            row["option_d"],
            correct_option_to_letter(row["correct_option"]),
            row["category"],
            row["difficulty"],
            row["is_active"],
            row["times_used"],
        ))

    return result


def get_question_by_id(question_id: int) -> Optional[tuple]:
    with closing(get_conn()) as conn:
        row = conn.execute("""
            SELECT *
            FROM questions
            WHERE id = ?
        """, (question_id,)).fetchone()

        if not row:
            return None

        return (
            row["id"],
            row["question_text"],
            row["option_a"],
            row["option_b"],
            row["option_c"],
            row["option_d"],
            correct_option_to_letter(row["correct_option"]),
            row["category"],
            row["difficulty"],
            row["is_active"],
            row["times_used"],
        )


def update_question(
    question_id: int,
    question_text: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    correct_option,
) -> bool:
    correct_option = normalize_correct_option(correct_option)

    with closing(get_conn()) as conn, conn:
        cur = conn.execute("""
            UPDATE questions
            SET question_text = ?,
                option_a = ?,
                option_b = ?,
                option_c = ?,
                option_d = ?,
                correct_option = ?
            WHERE id = ?
        """, (
            question_text.strip(),
            option_a.strip(),
            option_b.strip(),
            option_c.strip(),
            option_d.strip(),
            correct_option,
            question_id,
        ))
        return cur.rowcount > 0


def deactivate_question(question_id: int) -> bool:
    with closing(get_conn()) as conn, conn:
        cur = conn.execute("""
            UPDATE questions
            SET is_active = 0
            WHERE id = ? AND is_active = 1
        """, (question_id,))
        return cur.rowcount > 0


def activate_question(question_id: int) -> bool:
    with closing(get_conn()) as conn, conn:
        cur = conn.execute("""
            UPDATE questions
            SET is_active = 1
            WHERE id = ?
        """, (question_id,))
        return cur.rowcount > 0


def delete_question(question_id: int) -> bool:
    return deactivate_question(question_id)


def get_question_count() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()
        return row["c"] if row else 0


# -------------------------
# Game history functions
# -------------------------

def create_game(chat_id: int, total_players: int = 0, total_rounds: int = 0, status: str = "running") -> int:
    with closing(get_conn()) as conn, conn:
        cur = conn.execute("""
            INSERT INTO games (chat_id, total_players, total_rounds, status)
            VALUES (?, ?, ?, ?)
        """, (chat_id, total_players, total_rounds, status))
        return cur.lastrowid


def finish_game(
    game_id: int,
    winner_user_id: Optional[int],
    total_players: int,
    total_rounds: int,
    status: str = "finished"
):
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE games
            SET ended_at = CURRENT_TIMESTAMP,
                winner_user_id = ?,
                total_players = ?,
                total_rounds = ?,
                status = ?
            WHERE id = ?
        """, (winner_user_id, total_players, total_rounds, status, game_id))


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
        conn.execute("""
            INSERT INTO game_results (
                game_id, user_id, score, correct_count, wrong_count, avg_answer_time, position
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            game_id, user_id, score, correct_count, wrong_count, avg_answer_time, position
        ))


def get_total_games() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM games").fetchone()
        return row["c"] if row else 0


def get_total_players() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM players").fetchone()
        return row["c"] if row else 0