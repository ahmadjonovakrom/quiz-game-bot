from contextlib import closing
from typing import List, Optional
import logging

from config import ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES
from .connection import get_conn

logger = logging.getLogger(__name__)


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


def normalize_question_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def normalize_category(value: str) -> str:
    value = (value or "mixed").strip().lower()
    if value not in ALLOWED_CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(ALLOWED_CATEGORIES)}")
    return value


def normalize_difficulty(value: str) -> str:
    value = (value or "easy").strip().lower()
    if value not in ALLOWED_DIFFICULTIES:
        raise ValueError(f"difficulty must be one of: {', '.join(ALLOWED_DIFFICULTIES)}")
    return value


def question_exists(question_text: str) -> bool:
    normalized = normalize_question_text(question_text)

    with closing(get_conn()) as conn:
        rows = conn.execute("""
            SELECT question_text
            FROM questions
        """).fetchall()

        for row in rows:
            if normalize_question_text(row["question_text"]) == normalized:
                return True

        return False


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
    category = normalize_category(category)
    difficulty = normalize_difficulty(difficulty)

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

    normalized_category = (category or "").strip().lower()
    normalized_difficulty = (difficulty or "").strip().lower()

    if normalized_category and normalized_category != "mixed":
        query += " AND LOWER(TRIM(category)) = ?"
        params.append(normalized_category)

    if normalized_difficulty and normalized_difficulty != "mixed":
        query += " AND LOWER(TRIM(difficulty)) = ?"
        params.append(normalized_difficulty)

    if exclude_ids:
        placeholders = ",".join("?" for _ in exclude_ids)
        query += f" AND id NOT IN ({placeholders})"
        params.extend(exclude_ids)

    query += " ORDER BY times_used ASC, RANDOM() LIMIT 1"

    logger.warning(
        "GET_RANDOM_QUESTION category=%s difficulty=%s exclude_count=%s",
        normalized_category or None,
        normalized_difficulty or None,
        len(exclude_ids or []),
    )

    with closing(get_conn()) as conn, conn:
        row = conn.execute(query, params).fetchone()

        if row:
            conn.execute("""
                UPDATE questions
                SET times_used = times_used + 1
                WHERE id = ?
            """, (row["id"],))
            logger.warning(
                "QUESTION FOUND id=%s category=%s difficulty=%s",
                row["id"],
                row["category"],
                row["difficulty"],
            )
        else:
            logger.warning(
                "NO QUESTION FOUND query=%s params=%s",
                " ".join(query.split()),
                params,
            )

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

    normalized_category = (category or "").strip().lower()
    normalized_difficulty = (difficulty or "").strip().lower()

    if active_only:
        query += " AND is_active = 1"

    if normalized_category and normalized_category != "mixed":
        query += " AND LOWER(TRIM(category)) = ?"
        params.append(normalized_category)

    if normalized_difficulty and normalized_difficulty != "mixed":
        query += " AND LOWER(TRIM(difficulty)) = ?"
        params.append(normalized_difficulty)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with closing(get_conn()) as conn:
        return conn.execute(query, params).fetchall()


def list_questions_paginated(
    limit: int = 20,
    offset: int = 0,
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

    normalized_category = (category or "").strip().lower()
    normalized_difficulty = (difficulty or "").strip().lower()

    if active_only:
        query += " AND is_active = 1"

    if normalized_category and normalized_category != "mixed":
        query += " AND LOWER(TRIM(category)) = ?"
        params.append(normalized_category)

    if normalized_difficulty and normalized_difficulty != "mixed":
        query += " AND LOWER(TRIM(difficulty)) = ?"
        params.append(normalized_difficulty)

    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

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
    category: str = "mixed",
    difficulty: str = "easy",
) -> bool:
    correct_option = normalize_correct_option(correct_option)
    category = normalize_category(category)
    difficulty = normalize_difficulty(difficulty)

    with closing(get_conn()) as conn, conn:
        cur = conn.execute("""
            UPDATE questions
            SET question_text = ?,
                option_a = ?,
                option_b = ?,
                option_c = ?,
                option_d = ?,
                correct_option = ?,
                category = ?,
                difficulty = ?
            WHERE id = ?
        """, (
            question_text.strip(),
            option_a.strip(),
            option_b.strip(),
            option_c.strip(),
            option_d.strip(),
            correct_option,
            category,
            difficulty,
            question_id,
        ))
        return cur.rowcount > 0


def search_questions_by_keyword(keyword: str, limit: int = 15) -> List[tuple]:
    keyword = (keyword or "").strip()
    if not keyword:
        return []

    like_value = f"%{keyword.lower()}%"

    with closing(get_conn()) as conn:
        rows = conn.execute("""
            SELECT *
            FROM questions
            WHERE is_active = 1
            AND (
                LOWER(question_text) LIKE ?
                OR LOWER(option_a) LIKE ?
                OR LOWER(option_b) LIKE ?
                OR LOWER(option_c) LIKE ?
                OR LOWER(option_d) LIKE ?
                OR LOWER(category) LIKE ?
                OR LOWER(difficulty) LIKE ?
            )
            ORDER BY id DESC
            LIMIT ?
        """, (
            like_value,
            like_value,
            like_value,
            like_value,
            like_value,
            like_value,
            like_value,
            limit,
        )).fetchall()

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


def export_questions_to_rows() -> List[dict]:
    with closing(get_conn()) as conn:
        rows = conn.execute("""
            SELECT *
            FROM questions
            ORDER BY id ASC
        """).fetchall()

        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "question_text": row["question_text"],
                "option_a": row["option_a"],
                "option_b": row["option_b"],
                "option_c": row["option_c"],
                "option_d": row["option_d"],
                "correct_option": correct_option_to_letter(row["correct_option"]),
                "category": row["category"],
                "difficulty": row["difficulty"],
                "is_active": row["is_active"],
                "times_used": row["times_used"],
            })
        return result


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


def activate_all_questions() -> int:
    with closing(get_conn()) as conn, conn:
        cur = conn.execute("""
            UPDATE questions
            SET is_active = 1
        """)
        return cur.rowcount


def get_question_count() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()
        return row["c"] if row else 0


def get_total_questions_count() -> int:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM questions").fetchone()
        return row["count"] if row else 0