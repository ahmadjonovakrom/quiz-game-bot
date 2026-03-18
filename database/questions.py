from contextlib import closing
from typing import List, Optional

from .connection import get_conn


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

    category = (category or "mixed").strip().lower()
    difficulty = (difficulty or "easy").strip().lower()

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
            category,
            difficulty,
            created_by,
        ))


def get_random_question(
    exclude_ids: Optional[List[int]] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
):
    query = """
        SELECT *
        FROM questions
        WHERE is_active = 1
    """
    params = []

    if category and category != "mixed":
        query += " AND category = ?"
        params.append(category.strip().lower())

    if difficulty and difficulty != "mixed":
        query += " AND difficulty = ?"
        params.append(difficulty.strip().lower())

    if exclude_ids:
        placeholders = ",".join("?" for _ in exclude_ids)
        query += f" AND id NOT IN ({placeholders})"
        params.extend(exclude_ids)

    query += " ORDER BY times_used ASC, RANDOM() LIMIT 1"

    with closing(get_conn()) as conn, conn:
        row = conn.execute(query, params).fetchone()

        if row:
            conn.execute("""
                UPDATE questions
                SET times_used = times_used + 1
                WHERE id = ?
            """, (row["id"],))

        return row


def list_questions(
    limit: int = 20,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    active_only: bool = False,
):
    query = """
        SELECT *
        FROM questions
        WHERE 1=1
    """
    params = []

    if active_only:
        query += " AND is_active = 1"

    if category and category != "mixed":
        query += " AND category = ?"
        params.append(category.strip().lower())

    if difficulty and difficulty != "mixed":
        query += " AND difficulty = ?"
        params.append(difficulty.strip().lower())

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with closing(get_conn()) as conn:
        return conn.execute(query, params).fetchall()


def get_all_questions(limit: int = 50) -> List[tuple]:
    rows = list_questions(limit=limit)
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


def get_total_questions_count() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM questions").fetchone()
        return row["count"] if row else 0