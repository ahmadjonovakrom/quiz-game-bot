import csv
import io

from config import ALLOWED_CATEGORIES, ALLOWED_DIFFICULTIES
from database import (
    add_question,
    question_exists,
    get_all_questions,
    get_question_by_id,
    update_question,
    delete_question,
    activate_question,
    deactivate_question,
)
from database.questions import (
    search_questions_by_keyword,
    export_questions_to_rows,
)


def normalize_text(value: str, default: str = "") -> str:
    value = (value or "").strip()
    return value if value else default


def normalize_correct_option(value: str) -> str:
    value = normalize_text(value).upper()
    mapping = {
        "1": "A",
        "2": "B",
        "3": "C",
        "4": "D",
    }
    return mapping.get(value, value)


def create_question_service(data: dict):
    question_text = normalize_text(data.get("question_text"))
    option_a = normalize_text(data.get("option_a"))
    option_b = normalize_text(data.get("option_b"))
    option_c = normalize_text(data.get("option_c"))
    option_d = normalize_text(data.get("option_d"))
    correct_option = normalize_correct_option(data.get("correct_option"))
    category = normalize_text(data.get("category"), "mixed").lower()
    difficulty = normalize_text(data.get("difficulty"), "easy").lower()

    if not all([question_text, option_a, option_b, option_c, option_d]):
        return {"ok": False, "message": "All question fields are required."}

    if correct_option not in ("A", "B", "C", "D"):
        return {"ok": False, "message": "Correct option must be A, B, C, or D."}

    if category not in ALLOWED_CATEGORIES:
        return {"ok": False, "message": f"Invalid category. Allowed: {', '.join(ALLOWED_CATEGORIES)}"}

    if difficulty not in ALLOWED_DIFFICULTIES:
        return {"ok": False, "message": f"Invalid difficulty. Allowed: {', '.join(ALLOWED_DIFFICULTIES)}"}

    if question_exists(question_text):
        return {"ok": False, "message": "⚠️ This question already exists. Skipped."}

    add_question(
        question_text=question_text,
        option_a=option_a,
        option_b=option_b,
        option_c=option_c,
        option_d=option_d,
        correct_option=correct_option,
        category=category,
        difficulty=difficulty,
        created_by=data.get("created_by"),
    )

    return {"ok": True, "message": "✅ Question added successfully."}


def get_question_details_service(qid: int):
    q = get_question_by_id(qid)
    if not q:
        return {"ok": False, "message": "Question not found."}
    return {"ok": True, "data": q}


def list_questions_service(limit: int = 15):
    return get_all_questions(limit=limit)


def update_question_service(qid: int, data: dict):
    q = get_question_by_id(qid)
    if not q:
        return {"ok": False, "message": "Question not found."}

    question_text = normalize_text(data.get("question_text"))
    option_a = normalize_text(data.get("option_a"))
    option_b = normalize_text(data.get("option_b"))
    option_c = normalize_text(data.get("option_c"))
    option_d = normalize_text(data.get("option_d"))
    correct_option = normalize_correct_option(data.get("correct_option"))
    category = normalize_text(data.get("category"), "mixed").lower()
    difficulty = normalize_text(data.get("difficulty"), "easy").lower()

    if not all([question_text, option_a, option_b, option_c, option_d]):
        return {"ok": False, "message": "All question fields are required."}

    if correct_option not in ("A", "B", "C", "D"):
        return {"ok": False, "message": "Correct option must be A, B, C, or D."}

    if category not in ALLOWED_CATEGORIES:
        return {"ok": False, "message": f"Invalid category. Allowed: {', '.join(ALLOWED_CATEGORIES)}"}

    if difficulty not in ALLOWED_DIFFICULTIES:
        return {"ok": False, "message": f"Invalid difficulty. Allowed: {', '.join(ALLOWED_DIFFICULTIES)}"}

    updated = update_question(
        qid,
        question_text,
        option_a,
        option_b,
        option_c,
        option_d,
        correct_option,
        category,
        difficulty,
    )

    if not updated:
        return {"ok": False, "message": "❌ Failed to update question."}

    return {"ok": True, "message": "✅ Question updated successfully."}


def delete_question_service(qid: int):
    q = get_question_by_id(qid)
    if not q:
        return {"ok": False, "message": "Question not found."}

    delete_question(qid)
    return {"ok": True, "message": "✅ Question deleted successfully."}


def toggle_question_status_service(qid: int, action: str):
    q = get_question_by_id(qid)
    if not q:
        return {"ok": False, "message": "Question not found."}

    if action == "activate":
        activate_question(qid)
    elif action == "deactivate":
        deactivate_question(qid)
    else:
        return {"ok": False, "message": "Invalid action."}

    updated = get_question_by_id(qid)
    return {"ok": True, "data": updated}


def search_questions_service(keyword: str, limit: int = 15):
    keyword = normalize_text(keyword)
    if not keyword:
        return {"ok": False, "message": "Please send a keyword."}

    results = search_questions_by_keyword(keyword, limit=limit)
    return {"ok": True, "keyword": keyword, "results": results}


def export_questions_service():
    return export_questions_to_rows()


def import_questions_from_csv_service(csv_text: str, created_by: int | None = None):
    reader = csv.DictReader(io.StringIO(csv_text))

    required_columns = {
        "question_text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_option",
        "category",
        "difficulty",
    }

    if not reader.fieldnames:
        return {"ok": False, "message": "CSV file is empty or invalid."}

    fieldnames = {name.strip() for name in reader.fieldnames if name}
    missing = required_columns - fieldnames
    if missing:
        return {
            "ok": False,
            "message": "Missing required columns:\n" + "\n".join(sorted(missing)),
        }

    imported = 0
    duplicate_skipped = 0
    invalid_skipped = 0
    errors = []

    for row_number, row in enumerate(reader, start=2):
        try:
            normalized_row = {(k or "").strip(): v for k, v in row.items()}

            payload = {
                "question_text": normalize_text(normalized_row.get("question_text")),
                "option_a": normalize_text(normalized_row.get("option_a")),
                "option_b": normalize_text(normalized_row.get("option_b")),
                "option_c": normalize_text(normalized_row.get("option_c")),
                "option_d": normalize_text(normalized_row.get("option_d")),
                "correct_option": normalize_correct_option(normalized_row.get("correct_option")),
                "category": normalize_text(normalized_row.get("category"), "mixed").lower(),
                "difficulty": normalize_text(normalized_row.get("difficulty"), "easy").lower(),
                "created_by": created_by,
            }

            result = create_question_service(payload)

            if result["ok"]:
                imported += 1
            else:
                msg = result["message"].lower()
                if "already exists" in msg:
                    duplicate_skipped += 1
                else:
                    invalid_skipped += 1
                    errors.append(f"Row {row_number}: {result['message']}")

        except Exception as e:
            invalid_skipped += 1
            errors.append(f"Row {row_number}: {str(e)}")

    return {
        "ok": True,
        "imported": imported,
        "duplicate_skipped": duplicate_skipped,
        "invalid_skipped": invalid_skipped,
        "errors": errors,
    }