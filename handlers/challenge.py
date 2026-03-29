import html
import logging
import secrets
import time
import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import get_random_question

logger = logging.getLogger(__name__)

DUEL_ALLOWED_QUESTION_COUNTS = [5, 10, 15]
DUEL_ALLOWED_CATEGORIES = [
    "mixed",
    "vocabulary",
    "grammar",
    "idioms_phrases",
    "synonyms",
    "collocations",
]
DUEL_ALLOWED_DIFFICULTIES = ["mixed", "easy", "medium", "hard"]

CATEGORY_LABELS = {
    "mixed": "Mixed",
    "vocabulary": "Vocabulary",
    "grammar": "Grammar",
    "idioms_phrases": "Idioms & Phrases",
    "synonyms": "Synonyms",
    "collocations": "Collocations",
}

DIFFICULTY_LABELS = {
    "mixed": "Mixed",
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
}

active_duels = {}
user_active_duel = {}


def get_display_name(user):
    if user.username:
        return f"@{user.username}"
    return html.escape(user.full_name or "Player")


def make_duel_id():
    return secrets.token_hex(4)


def duel_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ Start Setup", callback_data="duel_setup_start")],
        [InlineKeyboardButton("◀️ Back", callback_data="menu_back")],
    ])


def duel_count_keyboard():
    rows = [[InlineKeyboardButton(str(n), callback_data=f"duel_setup_count:{n}")]
            for n in DUEL_ALLOWED_QUESTION_COUNTS]
    rows.append([InlineKeyboardButton("◀️ Back", callback_data="duel_setup_back_menu")])
    return InlineKeyboardMarkup(rows)


def duel_category_keyboard():
    rows = [
        [InlineKeyboardButton("Mixed", callback_data="duel_setup_category:mixed")],
        [InlineKeyboardButton("Vocabulary", callback_data="duel_setup_category:vocabulary")],
        [InlineKeyboardButton("Grammar", callback_data="duel_setup_category:grammar")],
        [InlineKeyboardButton("Idioms & Phrases", callback_data="duel_setup_category:idioms_phrases")],
        [InlineKeyboardButton("Synonyms", callback_data="duel_setup_category:synonyms")],
        [InlineKeyboardButton("Collocations", callback_data="duel_setup_category:collocations")],
        [InlineKeyboardButton("◀️ Back", callback_data="duel_setup_back_count")],
    ]
    return InlineKeyboardMarkup(rows)


def duel_difficulty_keyboard():
    rows = [
        [InlineKeyboardButton("Mixed", callback_data="duel_setup_difficulty:mixed")],
        [InlineKeyboardButton("Easy", callback_data="duel_setup_difficulty:easy")],
        [InlineKeyboardButton("Medium", callback_data="duel_setup_difficulty:medium")],
        [InlineKeyboardButton("Hard", callback_data="duel_setup_difficulty:hard")],
        [InlineKeyboardButton("◀️ Back", callback_data="duel_setup_back_category")],
    ]
    return InlineKeyboardMarkup(rows)


def duel_confirm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Create Challenge", callback_data="duel_create")],
        [InlineKeyboardButton("◀️ Back", callback_data="duel_setup_back_difficulty")],
    ])


def duel_lobby_keyboard(duel_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Join Challenge", callback_data=f"duel_join:{duel_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"duel_cancel:{duel_id}")],
    ])


def format_duel_ready_text(duel):
    return f"⚔️ <b>Challenge Accepted</b>\n\n{duel['creator_name']} vs {duel['opponent_name']}"


def format_question_result_text(duel, question_number, correct_option):
    p1 = duel["creator_id"]
    p2 = duel["opponent_id"]

    a1 = duel["answers"][question_number - 1].get(p1)
    a2 = duel["answers"][question_number - 1].get(p2)

    def mark(ans):
        if not ans:
            return "❌ No answer"
        return "✅ Correct" if ans["is_correct"] else "❌ Wrong"

    return (
        f"📊 <b>Question {question_number} Result</b>\n\n"
        f"{duel['creator_name']}: {mark(a1)}\n"
        f"{duel['opponent_name']}: {mark(a2)}\n\n"
        f"Correct answer: <b>{correct_option}</b>\n\n"
        f"Score:\n"
        f"{duel['creator_name']}: {duel['players'][p1]['correct']}\n"
        f"{duel['opponent_name']}: {duel['players'][p2]['correct']}"
    )


def format_duel_result_text(duel):
    p1 = duel["creator_id"]
    p2 = duel["opponent_id"]

    s1 = duel["players"][p1]
    s2 = duel["players"][p2]

    winner = "Draw"
    if s1["correct"] > s2["correct"]:
        winner = duel["creator_name"]
    elif s2["correct"] > s1["correct"]:
        winner = duel["opponent_name"]

    return (
        f"🏆 <b>Duel Results</b>\n\n"
        f"{duel['creator_name']}: {s1['correct']}\n"
        f"{duel['opponent_name']}: {s2['correct']}\n\n"
        f"Winner: {winner}"
    )


def cleanup_duel(duel_id):
    duel = active_duels.pop(duel_id, None)
    if duel:
        user_active_duel.pop(duel["creator_id"], None)
        if duel.get("opponent_id"):
            user_active_duel.pop(duel["opponent_id"], None)


def pick_duel_questions(count):
    used = set()
    result = []

    for _ in range(count):
        q = get_random_question(exclude_ids=list(used))
        if not q:
            return None
        result.append(q)
        used.add(q["id"])

    return result


async def duel_question_timeout(context, duel_id, q_index):
    await asyncio.sleep(18)

    duel = active_duels.get(duel_id)
    if not duel or duel["current_question"] != q_index:
        return

    answers = duel["answers"][q_index]

    for uid in [duel["creator_id"], duel["opponent_id"]]:
        if uid not in answers:
            answers[uid] = {"is_correct": False}
            duel["players"][uid]["wrong"] += 1

    correct_option = duel["questions"][q_index]["correct_option"] - 1
    label = ["A", "B", "C", "D"][correct_option]

    await context.bot.send_message(
        chat_id=duel["chat_id"],
        text=format_question_result_text(duel, q_index + 1, label),
        parse_mode="HTML",
    )

    duel["current_question"] += 1

    if duel["current_question"] >= duel["questions_count"]:
        await context.bot.send_message(
            duel["chat_id"],
            format_duel_result_text(duel),
            parse_mode="HTML",
        )
        cleanup_duel(duel_id)
    else:
        await send_next_duel_question(context, duel_id)


async def send_next_duel_question(context, duel_id):
    duel = active_duels.get(duel_id)
    if not duel:
        return

    q_index = duel["current_question"]
    q = duel["questions"][q_index]

    duel["question_started_at"] = time.time()

    poll = await context.bot.send_poll(
        chat_id=duel["chat_id"],
        question=q["question_text"],
        options=[
            f"A) {q['option_a']}",
            f"B) {q['option_b']}",
            f"C) {q['option_c']}",
            f"D) {q['option_d']}",
        ],
        type="quiz",
        correct_option_id=q["correct_option"] - 1,
        is_anonymous=False,
    )

    duel["current_poll_id"] = poll.poll.id

    asyncio.create_task(duel_question_timeout(context, duel_id, q_index))


async def handle_duel_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    uid = answer.user.id

    duel = None
    duel_id = None

    for d_id, d in active_duels.items():
        if d.get("current_poll_id") == answer.poll_id:
            duel = d
            duel_id = d_id
            break

    if not duel:
        return

    q_index = duel["current_question"]
    answers = duel["answers"][q_index]

    if uid in answers:
        return

    correct = duel["questions"][q_index]["correct_option"] - 1
    is_correct = answer.option_ids[0] == correct

    answers[uid] = {"is_correct": is_correct}

    if is_correct:
        duel["players"][uid]["correct"] += 1
    else:
        duel["players"][uid]["wrong"] += 1

    if (
        duel["creator_id"] in answers
        and duel["opponent_id"] in answers
    ):
        label = ["A", "B", "C", "D"][correct]

        await context.bot.send_message(
            duel["chat_id"],
            format_question_result_text(duel, q_index + 1, label),
            parse_mode="HTML",
        )

        duel["current_question"] += 1

        if duel["current_question"] >= duel["questions_count"]:
            await context.bot.send_message(
                duel["chat_id"],
                format_duel_result_text(duel),
                parse_mode="HTML",
            )
            cleanup_duel(duel_id)
        else:
            await send_next_duel_question(context, duel_id)