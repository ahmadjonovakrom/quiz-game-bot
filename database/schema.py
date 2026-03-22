from contextlib import closing

from .connection import get_conn


def _get_column_names(conn, table_name: str) -> set[str]:
    return {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def create_tables():
    with closing(get_conn()) as conn, conn:
        conn.execute("PRAGMA foreign_keys = ON")

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
                daily_streak INTEGER DEFAULT 0,
                best_daily_streak INTEGER DEFAULT 0,
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
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                chat_type TEXT NOT NULL,
                title TEXT,
                username TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
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
                wrong_answers INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                last_played_at TEXT,
                PRIMARY KEY (chat_id, user_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS group_points_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                points INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_points_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                points INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_quiz_attempts (
                user_id INTEGER NOT NULL,
                quiz_date TEXT NOT NULL,
                PRIMARY KEY (user_id, quiz_date)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_reward_claims (
                user_id INTEGER NOT NULL,
                reward_date TEXT NOT NULL,
                base_points INTEGER NOT NULL DEFAULT 0,
                bonus_points INTEGER NOT NULL DEFAULT 0,
                streak_after_claim INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, reward_date),
                FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        defaults = {
            "min_players": "1",
            "join_seconds": "60",
            "question_seconds": "15",
            "speed_bonus_seconds": "5",
            "speed_bonus_points": "5",
            "points_easy": "15",
            "points_medium": "25",
            "points_hard": "35",
        }

        for key, value in defaults.items():
            conn.execute("""
                INSERT OR IGNORE INTO settings (key, value)
                VALUES (?, ?)
            """, (key, value))

        question_columns = _get_column_names(conn, "questions")
        if "category" not in question_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN category TEXT DEFAULT 'mixed'")
        if "difficulty" not in question_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN difficulty TEXT DEFAULT 'easy'")
        if "created_by" not in question_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN created_by INTEGER")
        if "is_active" not in question_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN is_active INTEGER DEFAULT 1")
        if "times_used" not in question_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN times_used INTEGER DEFAULT 0")

        player_columns = _get_column_names(conn, "players")
        if "wrong_answers" not in player_columns:
            conn.execute("ALTER TABLE players ADD COLUMN wrong_answers INTEGER DEFAULT 0")
        if "current_streak" not in player_columns:
            conn.execute("ALTER TABLE players ADD COLUMN current_streak INTEGER DEFAULT 0")
        if "best_streak" not in player_columns:
            conn.execute("ALTER TABLE players ADD COLUMN best_streak INTEGER DEFAULT 0")
        if "daily_streak" not in player_columns:
            conn.execute("ALTER TABLE players ADD COLUMN daily_streak INTEGER DEFAULT 0")
        if "best_daily_streak" not in player_columns:
            conn.execute("ALTER TABLE players ADD COLUMN best_daily_streak INTEGER DEFAULT 0")
        if "fastest_answer_time" not in player_columns:
            conn.execute("ALTER TABLE players ADD COLUMN fastest_answer_time REAL")

        group_score_columns = _get_column_names(conn, "group_scores")
        if "wrong_answers" not in group_score_columns:
            conn.execute("ALTER TABLE group_scores ADD COLUMN wrong_answers INTEGER DEFAULT 0")

        group_points_history_columns = _get_column_names(conn, "group_points_history")
        if "created_at" not in group_points_history_columns:
            conn.execute(
                "ALTER TABLE group_points_history ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP"
            )

        player_points_history_columns = _get_column_names(conn, "player_points_history")
        if "created_at" not in player_points_history_columns:
            conn.execute(
                "ALTER TABLE player_points_history ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP"
            )

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_players_points
            ON players(total_points DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_players_rank_sort
            ON players(total_points DESC, correct_answers DESC, games_won DESC, user_id ASC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_category
            ON questions(category)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_difficulty
            ON questions(difficulty)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_questions_usage
            ON questions(times_used)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_games_chat_id
            ON games(chat_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_games_status
            ON games(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_scores_points
            ON group_scores(total_points DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_scores_rank
            ON group_scores(chat_id, total_points DESC, correct_answers DESC, games_won DESC, user_id ASC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_points_history_chat
            ON group_points_history(chat_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_points_history_created
            ON group_points_history(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_points_history_chat_created
            ON group_points_history(chat_id, created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_points_history_chat_user_created
            ON group_points_history(chat_id, user_id, created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_player_points_history_user
            ON player_points_history(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_player_points_history_created
            ON player_points_history(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_player_points_history_user_created
            ON player_points_history(user_id, created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_player_points_history_created_user
            ON player_points_history(created_at, user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_reward_claims_user_date
            ON daily_reward_claims(user_id, reward_date)
        """)