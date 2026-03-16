import sqlite3
import random
from config import DB_PATH


def get_connection():
    return sqlite3.connect(DB_PATH)


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_option TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        global_points INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_scores (
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        points INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )
    """)

    conn.commit()
    conn.close()


def add_question(question, a, b, c, d, correct):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (question, a, b, c, d, correct))

    conn.commit()
    conn.close()


def get_random_question():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM questions")
    questions = cursor.fetchall()

    conn.close()

    if not questions:
        return None

    return random.choice(questions)


def get_question_by_id(question_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
    question = cursor.fetchone()

    conn.close()
    return question


def ensure_player(user_id, username, full_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO players (user_id, username, full_name, global_points)
    VALUES (?, ?, ?, 0)
    ON CONFLICT(user_id) DO UPDATE SET
        username = excluded.username,
        full_name = excluded.full_name
    """, (user_id, username, full_name))

    conn.commit()
    conn.close()


def add_points(user_id, username, full_name, chat_id, points):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO players (user_id, username, full_name, global_points)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        username = excluded.username,
        full_name = excluded.full_name,
        global_points = global_points + excluded.global_points
    """, (user_id, username, full_name, points))

    cursor.execute("""
    INSERT INTO group_scores (chat_id, user_id, points)
    VALUES (?, ?, ?)
    ON CONFLICT(chat_id, user_id) DO UPDATE SET
        points = points + excluded.points
    """, (chat_id, user_id, points))

    conn.commit()
    conn.close()


def get_group_leaderboard(chat_id, limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT p.full_name, p.username, gs.points
    FROM group_scores gs
    JOIN players p ON gs.user_id = p.user_id
    WHERE gs.chat_id = ?
    ORDER BY gs.points DESC, p.full_name ASC
    LIMIT ?
    """, (chat_id, limit))

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_global_leaderboard(limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT full_name, username, global_points
    FROM players
    ORDER BY global_points DESC, full_name ASC
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()
    return rows