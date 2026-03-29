import html
import logging
import secrets
import time

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
    full_name = user.full_name or "Player"
    return html.escape(full_name)


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


def format_duel_menu_text():
    return (
        "⚔️ <b>1v1 Challenge</b>\n\n"
        "Set up your duel and open it to the group.\n\n"
        "The first player to join will become your opponent."
    )


def format_duel_confirm_text(settings):
    return (
        "⚔️ <b>Confirm Open Challenge</b>\n\n"
        f"Questions: <b>{settings['questions_count']}</b>\n"
        f"Category: <b>{CATEGORY_LABELS[settings['category']]}</b>\n"
        f"Difficulty: <b>{DIFFICULTY_LABELS[settings['difficulty']]}</b>\n\n"
        "The first player to join will face you."
    )


def format_duel_lobby_text(duel):
    creator_name = duel["creator_name"]
    opponent_name = duel["opponent_name"] or "Waiting for a player..."

    return (
        "⚔️ <b>Open Challenge Created</b>\n\n"
        f"👤 Creator: {creator_name}\n"
        f"👤 Opponent: {opponent_name}\n\n"
        "Duel Settings:\n"
        f"• Questions: <b>{duel['questions_count']}</b>\n"
        f"• Category: <b>{CATEGORY_LABELS[duel['category']]}</b>\n"
        f"• Difficulty: <b>{DIFFICULTY_LABELS[duel['difficulty']]}</b>\n\n"
        f"The first player to join will face {creator_name}."
    )


def format_duel_ready_text(duel):
    return (
        "⚔️ <b>Challenge Accepted</b>\n\n"
        f"{duel['creator_name']} vs {duel['opponent_name']}\n\n"
        "Starting in 3... 2... 1..."
    )


def format_question_header_text(duel, question_number):
    return (
        f"⚔️ <b>Duel • Question {question_number}/{duel['questions_count']}</b>"
    )


def format_question_result_text(duel, question_number, correct_option):
    p1 = duel["creator_id"]
    p2 = duel["opponent_id"]

    p1_name = duel["creator_name"]
    p2_name = duel["opponent_name"]

    a1 = duel["answers"][question_number - 1].get(p1)
    a2 = duel["answers"][question_number - 1].get(p2)

    def mark(ans):
        if not ans:
            return "❌ No answer"
        return "✅ Correct" if ans["is_correct"] else "❌ Wrong"

    return (
        f"📊 <b>Question {question_number} Result</b>\n\n"
        f"{p1_name}: {mark(a1)}\n"
        f"{p2_name}: {mark(a2)}\n\n"
        f"Correct answer: <b>{correct_option}</b>\n\n"
        f"⚔️ Score\n"
        f"{p1_name}: <b>{duel['players'][p1]['correct']}</b>\n"
        f"{p2_name}: <b>{duel['players'][p2]['correct']}</b>"
    )


def format_duel_result_text(duel):
    p1 = duel["creator_id"]
    p2 = duel["opponent_id"]
    s1 = duel["players"][p1]
    s2 = duel["players"][p2]
    p1_name = duel["creator_name"]
    p2_name = duel["opponent_name"]

    winner_id = get_duel_winner(duel)

    if winner_id is None:
        winner_line = "🤝 <b>Result: Draw</b>"
    elif winner_id == p1:
        winner_line = f"🏆 <b>Winner: {p1_name}</b>"
    else:
        winner_line = f"🏆 <b>Winner: {p2_name}</b>"

    return (
        "⚔️ <b>Duel Results</b>\n\n"
        f"{p1_name}\n"
        f"• Correct: {s1['correct']}/{duel['questions_count']}\n"
        f"• Wrong: {s1['wrong']}/{duel['questions_count']}\n"
        f"• Total time: {s1['total_time']:.1f}s\n\n"
        f"{p2_name}\n"
        f"• Correct: {s2['correct']}/{duel['questions_count']}\n"
        f"• Wrong: {s2['wrong']}/{duel['questions_count']}\n"
        f"• Total time: {s2['total_time']:.1f}s\n\n"
        f"{winner_line}"
    )


def get_duel_winner(duel):
    p1 = duel["creator_id"]
    p2 = duel["opponent_id"]
    s1 = duel["players"][p1]
    s2 = duel["players"][p2]

    if s1["correct"] > s2["correct"]:
        return p1
    if s2["correct"] > s1["correct"]:
        return p2
    if s1["total_time"] < s2["total_time"]:
        return p1
    if s2["total_time"] < s1["total_time"]:
        return p2
    return None


def cleanup_duel(duel_id):
    duel = active_duels.pop(duel_id, None)
    if not duel:
        return
    user_active_duel.pop(duel["creator_id"], None)
    if duel.get("opponent_id"):
        user_active_duel.pop(duel["opponent_id"], None)


def pick_duel_questions(count, category, difficulty):
    used_ids = set()
    picked = []

    for _ in range(count):
        q = get_random_question(
            category=None if category == "mixed" else category,
            difficulty=None if difficulty == "mixed" else difficulty,
            exclude_ids=list(used_ids),
        )
        if not q:
            return None
        picked.append(q)
        used_ids.add(q["id"])

    return picked


async def challenge_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["duel_setup"] = {
        "questions_count": 5,
        "category": "mixed",
        "difficulty": "mixed",
    }

    await query.edit_message_text(
        format_duel_menu_text(),
        reply_markup=duel_menu_keyboard(),
        parse_mode="HTML",
    )


async def duel_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user
    chat = query.message.chat

    if not data.startswith("duel_"):
        return False

    await query.answer()

    if data == "duel_setup_start":
        await query.edit_message_text(
            "⚔️ <b>Duel Setup</b>\n\nChoose number of questions:",
            reply_markup=duel_count_keyboard(),
            parse_mode="HTML",
        )
        return True

    if data == "duel_setup_back_menu":
        await query.edit_message_text(
            format_duel_menu_text(),
            reply_markup=duel_menu_keyboard(),
            parse_mode="HTML",
        )
        return True

    if data.startswith("duel_setup_count:"):
        count = int(data.split(":")[1])
        context.user_data.setdefault("duel_setup", {})
        context.user_data["duel_setup"]["questions_count"] = count

        await query.edit_message_text(
            "⚔️ <b>Duel Setup</b>\n\nChoose category:",
            reply_markup=duel_category_keyboard(),
            parse_mode="HTML",
        )
        return True

    if data == "duel_setup_back_count":
        await query.edit_message_text(
            "⚔️ <b>Duel Setup</b>\n\nChoose number of questions:",
            reply_markup=duel_count_keyboard(),
            parse_mode="HTML",
        )
        return True

    if data.startswith("duel_setup_category:"):
        category = data.split(":")[1]
        context.user_data.setdefault("duel_setup", {})
        context.user_data["duel_setup"]["category"] = category

        await query.edit_message_text(
            "⚔️ <b>Duel Setup</b>\n\nChoose difficulty:",
            reply_markup=duel_difficulty_keyboard(),
            parse_mode="HTML",
        )
        return True

    if data == "duel_setup_back_category":
        await query.edit_message_text(
            "⚔️ <b>Duel Setup</b>\n\nChoose category:",
            reply_markup=duel_category_keyboard(),
            parse_mode="HTML",
        )
        return True

    if data.startswith("duel_setup_difficulty:"):
        difficulty = data.split(":")[1]
        context.user_data.setdefault("duel_setup", {})
        context.user_data["duel_setup"]["difficulty"] = difficulty

        await query.edit_message_text(
            format_duel_confirm_text(context.user_data["duel_setup"]),
            reply_markup=duel_confirm_keyboard(),
            parse_mode="HTML",
        )
        return True

    if data == "duel_setup_back_difficulty":
        await query.edit_message_text(
            "⚔️ <b>Duel Setup</b>\n\nChoose difficulty:",
            reply_markup=duel_difficulty_keyboard(),
            parse_mode="HTML",
        )
        return True

    if data == "duel_create":
        if user.id in user_active_duel:
            await query.answer("You are already in an active duel.", show_alert=True)
            return True

        for duel in active_duels.values():
            if duel["chat_id"] == chat.id and duel["status"] in {"waiting", "running"}:
                await query.answer("There is already an active/open duel in this group.", show_alert=True)
                return True

        settings = context.user_data.get("duel_setup", {
            "questions_count": 5,
            "category": "mixed",
            "difficulty": "mixed",
        })

        questions = pick_duel_questions(
            settings["questions_count"],
            settings["category"],
            settings["difficulty"],
        )
        if not questions:
            await query.answer("Not enough questions for this setup.", show_alert=True)
            return True

        duel_id = make_duel_id()
        creator_name = get_display_name(user)

        duel = {
            "duel_id": duel_id,
            "chat_id": chat.id,
            "status": "waiting",
            "creator_id": user.id,
            "creator_name": creator_name,
            "opponent_id": None,
            "opponent_name": None,
            "questions_count": settings["questions_count"],
            "category": settings["category"],
            "difficulty": settings["difficulty"],
            "questions": questions,
            "current_question": 0,
            "answers": [{} for _ in range(settings["questions_count"])],
            "players": {
                user.id: {
                    "correct": 0,
                    "wrong": 0,
                    "total_time": 0.0,
                }
            },
            "question_started_at": None,
            "message_id": None,
            "current_poll_id": None,
            "current_poll_message_id": None,
            "current_poll_chat_id": None,
        }

        sent = await query.edit_message_text(
            format_duel_lobby_text(duel),
            reply_markup=duel_lobby_keyboard(duel_id),
            parse_mode="HTML",
        )

        duel["message_id"] = sent.message_id
        active_duels[duel_id] = duel
        user_active_duel[user.id] = duel_id
        return True

    if data.startswith("duel_cancel:"):
        duel_id = data.split(":")[1]
        duel = active_duels.get(duel_id)
        if not duel:
            await query.answer("This challenge no longer exists.", show_alert=True)
            return True

        if user.id != duel["creator_id"]:
            await query.answer("Only the creator can cancel this challenge.", show_alert=True)
            return True

        if duel["status"] != "waiting":
            await query.answer("You can only cancel before someone joins.", show_alert=True)
            return True

        await query.edit_message_text("❌ <b>Challenge cancelled.</b>", parse_mode="HTML")
        cleanup_duel(duel_id)
        return True

    if data.startswith("duel_join:"):
        duel_id = data.split(":")[1]
        duel = active_duels.get(duel_id)
        if not duel:
            await query.answer("This challenge no longer exists.", show_alert=True)
            return True

        if duel["status"] != "waiting":
            await query.answer("This challenge is not open anymore.", show_alert=True)
            return True

        if user.id == duel["creator_id"]:
            await query.answer("You cannot join your own challenge.", show_alert=True)
            return True

        if user.id in user_active_duel:
            await query.answer("You are already in an active duel.", show_alert=True)
            return True

        duel["opponent_id"] = user.id
        duel["opponent_name"] = get_display_name(user)
        duel["players"][user.id] = {
            "correct": 0,
            "wrong": 0,
            "total_time": 0.0,
        }
        duel["status"] = "running"
        user_active_duel[user.id] = duel_id

        await query.edit_message_text(
            format_duel_ready_text(duel),
            parse_mode="HTML",
        )

        await context.bot.send_message(chat_id=chat.id, text="⚔️ The duel begins now!")
        await send_next_duel_question(context, duel_id)
        return True

    return False


async def handle_duel_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    user_id = answer.user.id
    option_ids = answer.option_ids

    if not option_ids:
        return

    selected_option = option_ids[0]

    duel = None
    duel_id = None
    for current_duel_id, current_duel in active_duels.items():
        if current_duel.get("current_poll_id") == answer.poll_id:
            duel = current_duel
            duel_id = current_duel_id
            break

    if not duel or duel["status"] != "running":
        return

    if user_id not in {duel["creator_id"], duel["opponent_id"]}:
        return

    q_index = duel["current_question"]
    if q_index >= duel["questions_count"]:
        return

    answers_for_question = duel["answers"][q_index]
    if user_id in answers_for_question:
        return

    question = duel["questions"][q_index]
    correct_option_index = question["correct_option"] - 1

    if duel["question_started_at"] is None:
        elapsed = 0.0
    else:
        elapsed = max(0.0, time.time() - duel["question_started_at"])

    is_correct = selected_option == correct_option_index

    answers_for_question[user_id] = {
        "selected_option": selected_option + 1,
        "is_correct": is_correct,
        "time": elapsed,
    }

    if is_correct:
        duel["players"][user_id]["correct"] += 1
    else:
        duel["players"][user_id]["wrong"] += 1

    duel["players"][user_id]["total_time"] += elapsed

    creator_id = duel["creator_id"]
    opponent_id = duel["opponent_id"]

    if creator_id in answers_for_question and opponent_id in answers_for_question:
        correct_label = ["A", "B", "C", "D"][correct_option_index]

        await context.bot.send_message(
            chat_id=duel["chat_id"],
            text=format_question_result_text(duel, q_index + 1, correct_label),
            parse_mode="HTML",
        )

        duel["current_question"] += 1

        if duel["current_question"] >= duel["questions_count"]:
            duel["status"] = "finished"
            await context.bot.send_message(
                chat_id=duel["chat_id"],
                text=format_duel_result_text(duel),
                parse_mode="HTML",
            )
            cleanup_duel(duel_id)
        else:
            await send_next_duel_question(context, duel_id)


async def send_next_duel_question(context: ContextTypes.DEFAULT_TYPE, duel_id: str):
    duel = active_duels.get(duel_id)
    if not duel:
        return

    q_index = duel["current_question"]
    question_number = q_index + 1
    question = duel["questions"][q_index]

    await context.bot.send_message(
        chat_id=duel["chat_id"],
        text=format_question_header_text(duel, question_number),
        parse_mode="HTML",
    )

    options = [
        f"A) {question['option_a']}",
        f"B) {question['option_b']}",
        f"C) {question['option_c']}",
        f"D) {question['option_d']}",
    ]

    duel["question_started_at"] = time.time()

    poll_message = await context.bot.send_poll(
        chat_id=duel["chat_id"],
        question=question["question_text"],
        options=options,
        type="quiz",
        correct_option_id=question["correct_option"] - 1,
        is_anonymous=False,
    )

    duel["current_poll_id"] = poll_message.poll.id
    duel["current_poll_message_id"] = poll_message.message_id
    duel["current_poll_chat_id"] = poll_message.chat.id