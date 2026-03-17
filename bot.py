import asyncio
import logging
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    filters,
)

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    MIN_PLAYERS,
    JOIN_SECONDS,
    QUESTION_SECONDS,
    CORRECT_POINTS,
)

from database import (
    create_tables,
    add_question,
    get_random_question,
    get_question_by_id,
    get_all_questions,
    update_question,
    delete_question,
    ensure_player,
    add_points,
    get_group_leaderboard,
    get_global_leaderboard,
    get_player_profile,
    record_correct_answer,
    record_game_played,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUESTION, A, B, C, D, CORRECT = range(6)
EDIT_ID, EDIT_Q, EDIT_A, EDIT_B, EDIT_C, EDIT_D, EDIT_CORRECT = range(6, 13)
DELETE_ID = 13

ROUNDS_PER_GAME = 5

active_games = {}
poll_map = {}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def safe_task(coro):
    async def wrapper():
        try:
            await coro
        except Exception:
            logger.exception("Background task crashed")
    return asyncio.create_task(wrapper())


def build_join_text(game):
    if not game["players"]:
        return (
            "Registration is open\n\n"
            f"Joined:\nnone\n\n"
            f"Total: 0\n"
            f"Minimum needed: {MIN_PLAYERS}"
        )

    players_text = ", ".join(game["players"].values())

    return (
        "Registration is open\n\n"
        f"Joined:\n{players_text}\n\n"
        f"Total: {len(game['players'])}\n"
        f"Minimum needed: {MIN_PLAYERS}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Quiz Game Bot is running!")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(update.effective_user.id))


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Only admin can stop the game.")
        return

    if chat.id not in active_games:
        await update.message.reply_text("No game is currently running.")
        return

    game = active_games.get(chat.id)
    poll_id = game.get("current_poll_id")

    if poll_id in poll_map:
        poll_map.pop(poll_id, None)

    for pid in game.get("round_poll_ids", set()):
        poll_map.pop(pid, None)

    active_games.pop(chat.id, None)
    await update.message.reply_text("Game stopped.")


# =========================
# PROFILE / GLOBAL
# =========================
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    ensure_player(user.id, user.username, user.full_name)
    profile_data, rank = get_player_profile(user.id)

    if not profile_data:
        await update.message.reply_text("No profile data yet.")
        return

    full_name, username, global_points, games_played, correct_answers = profile_data
    display_name = f"@{username}" if username else full_name

    text = (
        "👤 Player Profile\n\n"
        f"Name: {display_name}\n"
        f"Games played: {games_played}\n"
        f"Correct answers: {correct_answers}\n"
        f"Total points: {global_points}\n"
        f"Global rank: #{rank}"
    )

    await update.message.reply_text(text)


async def global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_global_leaderboard()

    if not rows:
        await update.message.reply_text("No global scores yet.")
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🌍 Global Leaderboard\n\n"

    for i, row in enumerate(rows, start=1):
        name = f"@{row[1]}" if row[1] else row[0]
        prefix = medals[i - 1] if i <= 3 else f"{i}."
        text += f"{prefix} {name} — {row[2]} pts\n"

    await update.message.reply_text(text)


# =========================
# ADD QUESTION
# =========================
async def add_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("Send the question text:")
    return QUESTION


async def question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"] = update.message.text.strip()
    await update.message.reply_text("Option A:")
    return A


async def a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["a"] = update.message.text.strip()
    await update.message.reply_text("Option B:")
    return B


async def b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["b"] = update.message.text.strip()
    await update.message.reply_text("Option C:")
    return C


async def c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["c"] = update.message.text.strip()
    await update.message.reply_text("Option D:")
    return D


async def d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["d"] = update.message.text.strip()
    await update.message.reply_text("Correct option (A/B/C/D):")
    return CORRECT


async def correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()

    if correct not in ["A", "B", "C", "D"]:
        await update.message.reply_text("Send only A, B, C, or D.")
        return CORRECT

    add_question(
        context.user_data["q"],
        context.user_data["a"],
        context.user_data["b"],
        context.user_data["c"],
        context.user_data["d"],
        correct,
    )

    context.user_data.clear()
    await update.message.reply_text("Question added globally for all groups.")
    return ConversationHandler.END


async def cancel_add_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# =========================
# QUESTIONS LIST
# =========================
async def questions_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return

    rows = get_all_questions(limit=100)

    if not rows:
        await update.message.reply_text("No questions saved yet.")
        return

    chunks = []
    current = "📚 Saved Questions\n\n"

    for row in rows:
        qid, q, a, b, c, d, correct = row
        line = f"{qid}. {q} [Correct: {correct}]\n"
        if len(current) + len(line) > 3500:
            chunks.append(current)
            current = ""
        current += line

    if current:
        chunks.append(current)

    for chunk in chunks:
        await update.message.reply_text(chunk)


# =========================
# EDIT QUESTION
# =========================
async def edit_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("Send the question ID you want to edit:")
    return EDIT_ID


async def edit_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text("Send a valid numeric ID.")
        return EDIT_ID

    qid = int(text)
    row = get_question_by_id(qid)

    if not row:
        await update.message.reply_text("Question not found. Send another ID.")
        return EDIT_ID

    _, q, a, b, c, d, correct = row

    context.user_data["edit_id"] = qid
    context.user_data["q"] = q
    context.user_data["a"] = a
    context.user_data["b"] = b
    context.user_data["c"] = c
    context.user_data["d"] = d
    context.user_data["correct"] = correct

    await update.message.reply_text(
        f"Current question:\n\n"
        f"ID: {qid}\n"
        f"Q: {q}\n"
        f"A: {a}\n"
        f"B: {b}\n"
        f"C: {c}\n"
        f"D: {d}\n"
        f"Correct: {correct}\n\n"
        f"Now send the NEW question text:"
    )
    return EDIT_Q


async def edit_q_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"] = update.message.text.strip()
    await update.message.reply_text("Send new option A:")
    return EDIT_A


async def edit_a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["a"] = update.message.text.strip()
    await update.message.reply_text("Send new option B:")
    return EDIT_B


async def edit_b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["b"] = update.message.text.strip()
    await update.message.reply_text("Send new option C:")
    return EDIT_C


async def edit_c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["c"] = update.message.text.strip()
    await update.message.reply_text("Send new option D:")
    return EDIT_D


async def edit_d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["d"] = update.message.text.strip()
    await update.message.reply_text("Send the new correct option (A/B/C/D):")
    return EDIT_CORRECT


async def edit_correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()

    if correct not in ["A", "B", "C", "D"]:
        await update.message.reply_text("Send only A, B, C, or D.")
        return EDIT_CORRECT

    changed = update_question(
        context.user_data["edit_id"],
        context.user_data["q"],
        context.user_data["a"],
        context.user_data["b"],
        context.user_data["c"],
        context.user_data["d"],
        correct,
    )

    context.user_data.clear()

    if changed:
        await update.message.reply_text("Question updated successfully.")
    else:
        await update.message.reply_text("Question update failed.")
    return ConversationHandler.END


# =========================
# DELETE QUESTION
# =========================
async def delete_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    await update.message.reply_text("Send the question ID you want to delete:")
    return DELETE_ID


async def delete_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text("Send a valid numeric ID.")
        return DELETE_ID

    qid = int(text)
    row = get_question_by_id(qid)

    if not row:
        await update.message.reply_text("Question not found.")
        return ConversationHandler.END

    deleted = delete_question(qid)

    if deleted:
        await update.message.reply_text(f"Question {qid} deleted.")
    else:
        await update.message.reply_text("Delete failed.")

    return ConversationHandler.END


# =========================
# START GAME
# =========================
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await update.message.reply_text("Use /startgame inside a group.")
        return

    if chat.id in active_games:
        await update.message.reply_text(
            "A game is already running here.\nUse /stopgame to reset it."
        )
        return

    keyboard = [[InlineKeyboardButton("Join", callback_data=f"join|{chat.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text(
        build_join_text({"players": {}}),
        reply_markup=reply_markup,
        parse_mode="HTML",
    )

    try:
        await context.bot.pin_chat_message(
            chat_id=chat.id,
            message_id=msg.message_id,
            disable_notification=True
        )
    except Exception:
        pass

    active_games[chat.id] = {
        "status": "joining",
        "players": {},
        "scores": {},
        "round": 0,
        "answered": set(),
        "current_poll_id": None,
        "correct": None,
        "join_message_id": msg.message_id,
        "round_poll_ids": set(),
        "used_question_ids": set(),
    }

    safe_task(begin_game_after_join(chat.id, context))


async def begin_game_after_join(chat_id, context):
    await asyncio.sleep(JOIN_SECONDS)

    game = active_games.get(chat_id)
    if not game:
        return

    if game["status"] != "joining":
        return

    if len(game["players"]) < MIN_PLAYERS:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game["join_message_id"],
                text=build_join_text(game) + f"\n\nNot enough players. Need at least {MIN_PLAYERS}.",
                parse_mode="HTML",
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Not enough players (need {MIN_PLAYERS}).",
            )

        active_games.pop(chat_id, None)
        return

    game["status"] = "running"

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["join_message_id"],
            text=build_join_text(game) + "\n\nRegistration closed. Game starting...",
            parse_mode="HTML",
        )
    except Exception:
        await context.bot.send_message(chat_id, "Game starting!")

    await asyncio.sleep(2)
    await send_question(chat_id, context)


# =========================
# JOIN BUTTON
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("|")

    if data[0] != "join":
        await query.answer()
        return

    chat_id = int(data[1])
    game = active_games.get(chat_id)

    if not game:
        await query.answer("No active game.", show_alert=True)
        return

    if game["status"] != "joining":
        await query.answer("Joining time is over.", show_alert=True)
        return

    user = query.from_user

    if user.id in game["players"]:
        await query.answer("Already joined.")
        return

    name = f'<a href="tg://user?id={user.id}">{html.escape(user.first_name)}</a>'

    game["players"][user.id] = name
    game["scores"][user.id] = 0

    ensure_player(user.id, user.username, user.full_name)

    keyboard = [[InlineKeyboardButton("Join", callback_data=f"join|{chat_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["join_message_id"],
            text=build_join_text(game),
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    except Exception:
        pass

    await query.answer()


# =========================
# SEND QUESTION
# =========================
async def send_question(chat_id, context):
    game = active_games.get(chat_id)
    if not game:
        return

    game["round"] += 1

    if game["round"] > ROUNDS_PER_GAME:
        await end_game(chat_id, context)
        return

    question = get_random_question(exclude_ids=list(game["used_question_ids"]))
    if not question:
        await context.bot.send_message(
            chat_id,
            "Not enough unique questions left for this game. Ending early."
        )
        await end_game(chat_id, context)
        return

    q_id, q_text, a, b, c, d, correct = question
    game["used_question_ids"].add(q_id)

    options = [a, b, c, d]
    correct_index = ["A", "B", "C", "D"].index(correct)

    game["correct"] = correct_index
    game["answered"] = set()

    msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"[{game['round']}/{ROUNDS_PER_GAME}] {q_text}",
        options=options,
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False,
        open_period=QUESTION_SECONDS,
    )

    game["current_poll_id"] = msg.poll.id
    game["round_poll_ids"].add(msg.poll.id)
    poll_map[msg.poll.id] = {
        "chat_id": chat_id,
        "round": game["round"],
    }

    safe_task(next_question_timer(msg.poll.id, game["round"], context))


# =========================
# POLL ANSWERS
# =========================
async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id

    info = poll_map.get(poll_id)
    if not info:
        return

    chat_id = info["chat_id"]
    round_number = info["round"]

    game = active_games.get(chat_id)
    if not game:
        return

    if game["round"] != round_number:
        return

    if game["current_poll_id"] != poll_id:
        return

    user = answer.user

    if user.id not in game["players"]:
        return

    if user.id in game["answered"]:
        return

    game["answered"].add(user.id)

    if answer.option_ids and answer.option_ids[0] == game["correct"]:
        game["scores"][user.id] += CORRECT_POINTS

        add_points(
            user.id,
            user.username,
            user.full_name,
            chat_id,
            CORRECT_POINTS,
        )
        record_correct_answer(user.id)


# =========================
# NEXT QUESTION TIMER
# =========================
async def next_question_timer(poll_id, round_number, context):
    await asyncio.sleep(QUESTION_SECONDS + 2)

    info = poll_map.get(poll_id)
    if not info:
        return

    chat_id = info["chat_id"]
    game = active_games.get(chat_id)

    if not game:
        return

    if game["round"] != round_number:
        return

    if game["current_poll_id"] != poll_id:
        return

    await asyncio.sleep(2)
    await send_question(chat_id, context)


# =========================
# FINAL RESULTS
# =========================
async def end_game(chat_id, context):
    game = active_games.get(chat_id)
    if not game:
        return

    record_game_played(list(game["players"].keys()))

    ranking = sorted(
        game["scores"].items(),
        key=lambda x: x[1],
        reverse=True,
    )

    if not ranking:
        await context.bot.send_message(chat_id, "Game ended. Nobody scored any points.")
        active_games.pop(chat_id, None)
        return

    text = "🏆 Game Results\n\n"
    medals = ["🥇", "🥈", "🥉"]

    for i, (uid, pts) in enumerate(ranking[:3]):
        name = game["players"][uid]
        text += f"{medals[i]} {name} — {pts} 🍋\n"

    if len(ranking) > 3:
        for i, (uid, pts) in enumerate(ranking[3:], start=4):
            name = game["players"][uid]
            text += f"{i}. {name} — {pts} 🍋\n"

    await context.bot.send_message(chat_id, text.strip(), parse_mode="HTML")

    for pid in game.get("round_poll_ids", set()):
        poll_map.pop(pid, None)

    active_games.pop(chat_id, None)


# =========================
# LEADERBOARDS
# =========================
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_group_leaderboard(update.effective_chat.id)

    if not rows:
        await update.message.reply_text("No scores yet.")
        return

    text = "🏆 Leaderboard\n\n"

    for i, r in enumerate(rows, start=1):
        name = f"@{r[1]}" if r[1] else r[0]
        text += f"{i}. {name} — {r[2]} pts\n"

    await update.message.reply_text(text)


# =========================
# MAIN
# =========================
def main():
    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()

    add_q_handler = ConversationHandler(
        entry_points=[CommandHandler("addquestion", add_question_start)],
        states={
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_step)],
            A: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_step)],
            B: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_step)],
            C: [MessageHandler(filters.TEXT & ~filters.COMMAND, c_step)],
            D: [MessageHandler(filters.TEXT & ~filters.COMMAND, d_step)],
            CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, correct_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add_question)],
    )

    edit_q_handler = ConversationHandler(
        entry_points=[CommandHandler("editquestion", edit_question_start)],
        states={
            EDIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_id_step)],
            EDIT_Q: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_q_step)],
            EDIT_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_a_step)],
            EDIT_B: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_b_step)],
            EDIT_C: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_c_step)],
            EDIT_D: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_d_step)],
            EDIT_CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_correct_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add_question)],
    )

    delete_q_handler = ConversationHandler(
        entry_points=[CommandHandler("deletequestion", delete_question_start)],
        states={
            DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_id_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add_question)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("stopgame", stop_game))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("global", global_leaderboard))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("questions", questions_list))
    app.add_handler(CommandHandler("myid", myid))

    app.add_handler(add_q_handler)
    app.add_handler(edit_q_handler)
    app.add_handler(delete_q_handler)

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PollAnswerHandler(receive_poll_answer))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()