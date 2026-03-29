import html
import logging
import secrets
import time
import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database import add_points, get_random_question
from handlers.game_setup import load_dynamic_settings

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

# Base duel rewards
WINNER_REWARD = 50
LOSER_REWARD = 10
DRAW_REWARD = 25

active_duels = {}
user_active_duel = {}
finished_duels = {}


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
    rows = [
        [InlineKeyboardButton(str(n), callback_data=f"duel_setup_count:{n}")]
        for n in DUEL_ALLOWED_QUESTION_COUNTS
    ]
    rows.append([InlineKeyboardButton("◀️ Back", callback_data="duel_setup_back_menu")])
    return InlineKeyboardMarkup(rows)


def duel_category_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Mixed", callback_data="duel_setup_category:mixed")],
        [InlineKeyboardButton("Vocabulary", callback_data="duel_setup_category:vocabulary")],
        [InlineKeyboardButton("Grammar", callback_data="duel_setup_category:grammar")],
        [InlineKeyboardButton("Idioms & Phrases", callback_data="duel_setup_category:idioms_phrases")],
        [InlineKeyboardButton("Synonyms", callback_data="duel_setup_category:synonyms")],
        [InlineKeyboardButton("Collocations", callback_data="duel_setup_category:collocations")],
        [InlineKeyboardButton("◀️ Back", callback_data="duel_setup_back_count")],
    ])


def duel_difficulty_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Mixed", callback_data="duel_setup_difficulty:mixed")],
        [InlineKeyboardButton("Easy", callback_data="duel_setup_difficulty:easy")],
        [InlineKeyboardButton("Medium", callback_data="duel_setup_difficulty:medium")],
        [InlineKeyboardButton("Hard", callback_data="duel_setup_difficulty:hard")],
        [InlineKeyboardButton("◀️ Back", callback_data="duel_setup_back_category")],
    ])


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


def duel_result_keyboard(duel_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Rematch", callback_data=f"duel_rematch:{duel_id}")],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu_main")],
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
        "Get ready..."
    )


def format_question_header_text(duel, question_number, question_seconds):
    return (
        f"⚔️ <b>Duel • Question {question_number}/{duel['questions_count']}</b>\n"
        f"⏱ Time: <b>{question_seconds}s</b>\n"
        f"🏷 Category: <b>{CATEGORY_LABELS[duel['category']]}</b>\n"
        f"📈 Difficulty: <b>{DIFFICULTY_LABELS[duel['difficulty']]}</b>"
    )


def format_question_result_text(duel, question_number, correct_option, speed_bonus_text=""):
    p1 = duel["creator_id"]
    p2 = duel["opponent_id"]

    a1 = duel["answers"][question_number - 1].get(p1)
    a2 = duel["answers"][question_number - 1].get(p2)

    def mark(ans):
        if not ans:
            return "❌ No answer"
        return "✅ Correct" if ans["is_correct"] else "❌ Wrong"

    text = (
        f"📊 <b>Question {question_number} Result</b>\n\n"
        f"{duel['creator_name']}: {mark(a1)}\n"
        f"{duel['opponent_name']}: {mark(a2)}\n\n"
        f"Correct answer: <b>{correct_option}</b>\n"
    )

    if speed_bonus_text:
        text += f"\n{speed_bonus_text}\n"

    text += (
        f"\n⚔️ <b>Score</b>\n"
        f"{duel['creator_name']}: <b>{duel['players'][p1]['correct']}</b>\n"
        f"{duel['opponent_name']}: <b>{duel['players'][p2]['correct']}</b>"
    )
    return text


def get_duel_winner_id(duel):
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


def build_reward_map(duel):
    p1 = duel["creator_id"]
    p2 = duel["opponent_id"]
    winner_id = get_duel_winner_id(duel)

    rewards = {
        p1: duel["players"][p1]["speed_bonus_points"],
        p2: duel["players"][p2]["speed_bonus_points"],
    }

    if winner_id is None:
        rewards[p1] += DRAW_REWARD
        rewards[p2] += DRAW_REWARD
    elif winner_id == p1:
        rewards[p1] += WINNER_REWARD
        rewards[p2] += LOSER_REWARD
    else:
        rewards[p2] += WINNER_REWARD
        rewards[p1] += LOSER_REWARD

    return rewards


def format_duel_result_text(duel):
    p1 = duel["creator_id"]
    p2 = duel["opponent_id"]

    s1 = duel["players"][p1]
    s2 = duel["players"][p2]
    winner_id = get_duel_winner_id(duel)
    rewards = build_reward_map(duel)

    if winner_id == p1:
        winner_line = f"🏆 Winner: <b>{duel['creator_name']}</b>"
    elif winner_id == p2:
        winner_line = f"🏆 Winner: <b>{duel['opponent_name']}</b>"
    else:
        winner_line = "🤝 Result: <b>Draw</b>"

    return (
        "🏆 <b>Duel Results</b>\n\n"
        f"{duel['creator_name']}\n"
        f"• Correct: {s1['correct']}\n"
        f"• Wrong: {s1['wrong']}\n"
        f"• Time: {s1['total_time']:.1f}s\n"
        f"• Speed bonus: +{s1['speed_bonus_points']} 🍋\n"
        f"• Total reward: +{rewards[p1]} 🍋\n\n"
        f"{duel['opponent_name']}\n"
        f"• Correct: {s2['correct']}\n"
        f"• Wrong: {s2['wrong']}\n"
        f"• Time: {s2['total_time']:.1f}s\n"
        f"• Speed bonus: +{s2['speed_bonus_points']} 🍋\n"
        f"• Total reward: +{rewards[p2]} 🍋\n\n"
        f"{winner_line}"
    )


def cleanup_duel(duel_id):
    duel = active_duels.pop(duel_id, None)
    if duel:
        user_active_duel.pop(duel["creator_id"], None)
        if duel.get("opponent_id"):
            user_active_duel.pop(duel["opponent_id"], None)


def pick_duel_questions(count, category="mixed", difficulty="mixed"):
    used_ids = set()
    result = []

    for _ in range(count):
        q = get_random_question(
            category=None if category == "mixed" else category,
            difficulty=None if difficulty == "mixed" else difficulty,
            exclude_ids=list(used_ids),
        )
        if not q:
            return None
        result.append(q)
        used_ids.add(q["id"])

    return result


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


async def create_rematch_from_finished(context: ContextTypes.DEFAULT_TYPE, duel_id: str):
    finished = finished_duels.get(duel_id)
    if not finished:
        return False

    original_id = duel_id
    new_duel_id = make_duel_id()

    duel = {
        "duel_id": new_duel_id,
        "chat_id": finished["chat_id"],
        "status": "running",
        "creator_id": finished["creator_id"],
        "creator_name": finished["creator_name"],
        "opponent_id": finished["opponent_id"],
        "opponent_name": finished["opponent_name"],
        "questions_count": finished["questions_count"],
        "category": finished["category"],
        "difficulty": finished["difficulty"],
        "questions": pick_duel_questions(
            finished["questions_count"],
            finished["category"],
            finished["difficulty"],
        ),
        "current_question": 0,
        "answers": [{} for _ in range(finished["questions_count"])],
        "players": {
            finished["creator_id"]: {
                "correct": 0,
                "wrong": 0,
                "total_time": 0.0,
                "speed_bonus_points": 0,
                "speed_bonus_wins": 0,
            },
            finished["opponent_id"]: {
                "correct": 0,
                "wrong": 0,
                "total_time": 0.0,
                "speed_bonus_points": 0,
                "speed_bonus_wins": 0,
            },
        },
        "question_started_at": None,
        "current_poll_id": None,
    }

    if not duel["questions"]:
        return False

    active_duels[new_duel_id] = duel
    user_active_duel[duel["creator_id"]] = new_duel_id
    user_active_duel[duel["opponent_id"]] = new_duel_id

    finished_duels.pop(original_id, None)

    await context.bot.send_message(
        chat_id=duel["chat_id"],
        text=(
            "🔁 <b>Rematch Started</b>\n\n"
            f"{duel['creator_name']} vs {duel['opponent_name']}"
        ),
        parse_mode="HTML",
    )
    await send_next_duel_question(context, new_duel_id)
    return True


async def finalize_duel(context: ContextTypes.DEFAULT_TYPE, duel_id: str):
    duel = active_duels.get(duel_id)
    if not duel:
        return

    duel["status"] = "finished"
    rewards = build_reward_map(duel)

    for user_id, amount in rewards.items():
        if amount > 0:
            add_points(user_id, amount)

    finished_duels[duel_id] = {
        "chat_id": duel["chat_id"],
        "creator_id": duel["creator_id"],
        "creator_name": duel["creator_name"],
        "opponent_id": duel["opponent_id"],
        "opponent_name": duel["opponent_name"],
        "questions_count": duel["questions_count"],
        "category": duel["category"],
        "difficulty": duel["difficulty"],
        "rematch_requests": set(),
    }

    await context.bot.send_message(
        duel["chat_id"],
        format_duel_result_text(duel),
        parse_mode="HTML",
        reply_markup=duel_result_keyboard(duel_id),
    )

    cleanup_duel(duel_id)


async def finalize_duel_question(context: ContextTypes.DEFAULT_TYPE, duel_id: str, q_index: int):
    duel = active_duels.get(duel_id)
    if not duel:
        return

    if duel["current_question"] != q_index:
        return

    answers = duel["answers"][q_index]

    # fill missing answers
    for uid in [duel["creator_id"], duel["opponent_id"]]:
        if uid not in answers:
            answers[uid] = {
                "selected_option": None,
                "is_correct": False,
                "time": 999.0,
            }
            duel["players"][uid]["wrong"] += 1

    correct_option_index = duel["questions"][q_index]["correct_option"] - 1
    label = ["A", "B", "C", "D"][correct_option_index]

    # speed bonus: fastest correct answer gets extra lemons
    settings = load_dynamic_settings()
    speed_bonus_seconds = settings["SPEED_BONUS_SECONDS"]
    speed_bonus_points = settings["SPEED_BONUS_POINTS"]

    correct_answers = []
    for uid, data in answers.items():
        if data["is_correct"] and data["time"] <= speed_bonus_seconds:
            correct_answers.append((uid, data["time"]))

    speed_bonus_text = ""
    if correct_answers:
        correct_answers.sort(key=lambda x: x[1])
        bonus_user_id, bonus_time = correct_answers[0]
        duel["players"][bonus_user_id]["speed_bonus_points"] += speed_bonus_points
        duel["players"][bonus_user_id]["speed_bonus_wins"] += 1

        bonus_name = (
            duel["creator_name"] if bonus_user_id == duel["creator_id"]
            else duel["opponent_name"]
        )
        speed_bonus_text = (
            f"⚡ Speed bonus: <b>{bonus_name}</b> +{speed_bonus_points} 🍋 "
            f"({bonus_time:.1f}s)"
        )

    await context.bot.send_message(
        duel["chat_id"],
        format_question_result_text(duel, q_index + 1, label, speed_bonus_text),
        parse_mode="HTML",
    )

    duel["current_question"] += 1

    if duel["current_question"] >= duel["questions_count"]:
        await finalize_duel(context, duel_id)
    else:
        await send_next_duel_question(context, duel_id)


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
        duel = {
            "duel_id": duel_id,
            "chat_id": chat.id,
            "status": "waiting",
            "creator_id": user.id,
            "creator_name": get_display_name(user),
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
                    "speed_bonus_points": 0,
                    "speed_bonus_wins": 0,
                }
            },
            "question_started_at": None,
            "current_poll_id": None,
        }

        active_duels[duel_id] = duel
        user_active_duel[user.id] = duel_id

        await query.edit_message_text(
            format_duel_lobby_text(duel),
            reply_markup=duel_lobby_keyboard(duel_id),
            parse_mode="HTML",
        )
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
            "speed_bonus_points": 0,
            "speed_bonus_wins": 0,
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

    if data.startswith("duel_rematch:"):
        duel_id = data.split(":")[1]
        finished = finished_duels.get(duel_id)
        if not finished:
            await query.answer("This rematch is no longer available.", show_alert=True)
            return True

        if user.id not in {finished["creator_id"], finished["opponent_id"]}:
            await query.answer("This rematch is not for you.", show_alert=True)
            return True

        finished["rematch_requests"].add(user.id)

        if len(finished["rematch_requests"]) == 1:
            await query.answer("Rematch requested. Waiting for your opponent.")
            return True

        await query.answer("Rematch accepted!")
        ok = await create_rematch_from_finished(context, duel_id)
        if not ok:
            await context.bot.send_message(
                chat_id=finished["chat_id"],
                text="❌ Could not start rematch. Not enough questions available.",
            )
        return True

    return False


async def handle_duel_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    user_id = answer.user.id
    option_ids = answer.option_ids

    if not option_ids:
        return

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
    answers = duel["answers"][q_index]

    if user_id in answers:
        return

    selected_option = option_ids[0]
    correct_option_index = duel["questions"][q_index]["correct_option"] - 1

    elapsed = 0.0 if duel["question_started_at"] is None else max(0.0, time.time() - duel["question_started_at"])
    is_correct = selected_option == correct_option_index

    answers[user_id] = {
        "selected_option": selected_option + 1,
        "is_correct": is_correct,
        "time": elapsed,
    }

    if is_correct:
        duel["players"][user_id]["correct"] += 1
    else:
        duel["players"][user_id]["wrong"] += 1

    duel["players"][user_id]["total_time"] += elapsed

    if duel["creator_id"] in answers and duel["opponent_id"] in answers:
        await finalize_duel_question(context, duel_id, q_index)


async def duel_question_timeout(
    context: ContextTypes.DEFAULT_TYPE,
    duel_id: str,
    q_index: int,
    question_seconds: int,
):
    await asyncio.sleep(question_seconds + 1)

    duel = active_duels.get(duel_id)
    if not duel:
        return

    if duel["current_question"] != q_index:
        return

    await finalize_duel_question(context, duel_id, q_index)


async def send_next_duel_question(context: ContextTypes.DEFAULT_TYPE, duel_id: str):
    duel = active_duels.get(duel_id)
    if not duel:
        return

    settings = load_dynamic_settings()
    question_seconds = settings["QUESTION_SECONDS"]

    q_index = duel["current_question"]
    question_number = q_index + 1
    q = duel["questions"][q_index]

    await context.bot.send_message(
        chat_id=duel["chat_id"],
        text=format_question_header_text(duel, question_number, question_seconds),
        parse_mode="HTML",
    )

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
        open_period=question_seconds,
    )

    duel["current_poll_id"] = poll.poll.id

    asyncio.create_task(
        duel_question_timeout(context, duel_id, q_index, question_seconds)
    )