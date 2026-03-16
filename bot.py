import asyncio
import logging
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
    ensure_player,
    add_points,
    get_group_leaderboard,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUESTION, A, B, C, D, CORRECT = range(6)

ROUNDS_PER_GAME = 5

active_games = {}
poll_map = {}


# =========================
# SAFE TASK
# =========================
def safe_task(coro):
    async def wrapper():
        try:
            await coro
        except Exception:
            logger.exception("Background task crashed")
    return asyncio.create_task(wrapper())


# =========================
# BASIC COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Quiz Game Bot is running!")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(update.effective_user.id))


# =========================
# STOP GAME
# =========================
async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Only admin can stop the game.")
        return

    if chat.id not in active_games:
        await update.message.reply_text("No game is currently running.")
        return

    game = active_games.get(chat.id)

    poll_id = game.get("current_poll_id")
    if poll_id in poll_map:
        poll_map.pop(poll_id, None)

    active_games.pop(chat.id, None)

    await update.message.reply_text("Game stopped.")


# =========================
# ADD QUESTION
# =========================
async def add_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Admin only.")
        return ConversationHandler.END

    await update.message.reply_text("Send the question text:")
    return QUESTION


async def question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["q"] = update.message.text
    await update.message.reply_text("Option A:")
    return A


async def a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["a"] = update.message.text
    await update.message.reply_text("Option B:")
    return B


async def b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["b"] = update.message.text
    await update.message.reply_text("Option C:")
    return C


async def c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["c"] = update.message.text
    await update.message.reply_text("Option D:")
    return D


async def d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["d"] = update.message.text
    await update.message.reply_text("Correct option (A/B/C/D):")
    return CORRECT


async def correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):

    correct = update.message.text.upper()

    add_question(
        context.user_data["q"],
        context.user_data["a"],
        context.user_data["b"],
        context.user_data["c"],
        context.user_data["d"],
        correct,
    )

    await update.message.reply_text("Question added.")
    return ConversationHandler.END


# =========================
# START GAME
# =========================
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    if chat_id in active_games:
        await update.message.reply_text(
            "A game is already running here.\nUse /stopgame to reset it."
        )
        return

    active_games[chat_id] = {
        "status": "joining",
        "players": {},
        "scores": {},
        "round": 0,
        "answered": set(),
        "current_poll_id": None,
        "correct": None,
    }

    keyboard = [[InlineKeyboardButton("🎮 Join Game", callback_data=f"join|{chat_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"New quiz game!\n\nJoin within {JOIN_SECONDS} seconds.",
        reply_markup=reply_markup,
    )

    safe_task(begin_game_after_join(chat_id, context))


async def begin_game_after_join(chat_id, context):

    await asyncio.sleep(JOIN_SECONDS)

    game = active_games.get(chat_id)

    if not game:
        return

    if len(game["players"]) < MIN_PLAYERS:

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Not enough players (need {MIN_PLAYERS}).",
        )

        active_games.pop(chat_id, None)
        return

    await context.bot.send_message(chat_id, "Game starting!")

    await send_question(chat_id, context)


# =========================
# JOIN BUTTON
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data.split("|")

    if data[0] != "join":
        return

    chat_id = int(data[1])
    game = active_games.get(chat_id)

    if not game:
        return

    user = query.from_user

    if user.id in game["players"]:
        await query.answer("Already joined.", show_alert=True)
        return

    name = user.username or user.full_name

    game["players"][user.id] = name
    game["scores"][user.id] = 0

    ensure_player(user.id, user.username, user.full_name)

    await query.answer("Joined!", show_alert=True)


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

    question = get_random_question()

    if not question:
        await context.bot.send_message(chat_id, "No questions.")
        return

    q_id, q_text, a, b, c, d, correct = question

    options = [a, b, c, d]
    correct_index = ["A", "B", "C", "D"].index(correct)

    game["correct"] = correct_index
    game["answered"] = set()

    msg = await context.bot.send_poll(
        chat_id,
        question=f"Round {game['round']}/{ROUNDS_PER_GAME}\n\n{q_text}",
        options=options,
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False,
        open_period=QUESTION_SECONDS,
    )

    game["current_poll_id"] = msg.poll.id
    poll_map[msg.poll.id] = chat_id

    safe_task(next_question_timer(msg.poll.id, context))


# =========================
# POLL ANSWERS
# =========================
async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):

    answer = update.poll_answer
    poll_id = answer.poll_id

    if poll_id not in poll_map:
        return

    chat_id = poll_map[poll_id]
    game = active_games.get(chat_id)

    if not game:
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


# =========================
# NEXT QUESTION TIMER
# =========================
async def next_question_timer(poll_id, context):

    await asyncio.sleep(QUESTION_SECONDS + 2)

    chat_id = poll_map.get(poll_id)

    if not chat_id:
        return

    game = active_games.get(chat_id)

    if not game:
        return

    await send_round_leaderboard(chat_id, context)

    await asyncio.sleep(2)

    await send_question(chat_id, context)


async def send_round_leaderboard(chat_id, context):

    game = active_games.get(chat_id)

    ranking = sorted(
        game["scores"].items(),
        key=lambda x: x[1],
        reverse=True,
    )

    text = f"Leaderboard after round {game['round']}\n\n"

    for i, (uid, pts) in enumerate(ranking[:10]):
        name = game["players"][uid]
        text += f"{i+1}. {name} — {pts} pts\n"

    await context.bot.send_message(chat_id, text)


# =========================
# FINAL PODIUM
# =========================
async def end_game(chat_id, context):

    game = active_games.get(chat_id)

    ranking = sorted(
        game["scores"].items(),
        key=lambda x: x[1],
        reverse=True,
    )

    text = "🏆 Final Winners\n\n"

    medals = ["🥇", "🥈", "🥉"]

    for i, (uid, pts) in enumerate(ranking[:3]):
        name = game["players"][uid]
        text += f"{medals[i]} {name} — {pts} pts\n"

    await context.bot.send_message(chat_id, text)

    active_games.pop(chat_id, None)


# =========================
# LEADERBOARD
# =========================
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    rows = get_group_leaderboard(update.effective_chat.id)

    text = "🏆 Leaderboard\n\n"

    for i, r in enumerate(rows):
        name = r[1] or r[0]
        text += f"{i+1}. {name} — {r[2]} pts\n"

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
            QUESTION: [MessageHandler(filters.TEXT, question_step)],
            A: [MessageHandler(filters.TEXT, a_step)],
            B: [MessageHandler(filters.TEXT, b_step)],
            C: [MessageHandler(filters.TEXT, c_step)],
            D: [MessageHandler(filters.TEXT, d_step)],
            CORRECT: [MessageHandler(filters.TEXT, correct_step)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("stopgame", stop_game))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("myid", myid))

    app.add_handler(add_q_handler)

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PollAnswerHandler(receive_poll_answer))

    print("Bot running...")

    app.run_polling()


if __name__ == "__main__":
    main()