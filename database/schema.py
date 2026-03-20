from contextlib import closing

from .connection import get_conn


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
            CREATE TABLE IF NOT EXISTS daily_quiz_attempts (
                user_id INTEGER NOT NULL,
                quiz_date TEXT NOT NULL,
                PRIMARY KEY (user_id, quiz_date)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_points_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                points INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES players(user_id)
            )
        """)

        existing_columns = [
            row["name"]
            for row in conn.execute("PRAGMA table_info(questions)").fetchall()
        ]

        if "category" not in existing_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN category TEXT DEFAULT 'mixed'")

        if "difficulty" not in existing_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN difficulty TEXT DEFAULT 'easy'")

        if "created_by" not in existing_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN created_by INTEGER")

        if "is_active" not in existing_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN is_active INTEGER DEFAULT 1")

        if "times_used" not in existing_columns:
            conn.execute("ALTER TABLE questions ADD COLUMN times_used INTEGER DEFAULT 0")

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_players_points
            ON players(total_points DESC)
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
            CREATE INDEX IF NOT EXISTS idx_group_scores_points
            ON group_scores(total_points DESC)
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