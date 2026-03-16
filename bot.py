import asyncio
import time
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    MIN_PLAYERS,
    JOIN_SECONDS,
    QUESTION_SECONDS,
    SPEED_BONUS_SECONDS,
    CORRECT_POINTS,
    SPEED_BONUS_POINTS,
)

from database import (
    create_tables,
    add_question,
    get_random_question,
    ensure_player,
    add_points,
    get_group_leaderboard,
    get_global_leaderboard,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

QUESTION, A, B, C, D, CORRECT = range(6)

active_games = {}
user_last_click = {}

ROUNDS_PER_GAME = 5
SPAM_SECONDS = 1.0


def get_name(user):
    if user.username:
        return f"@{user.username}"
    return user.full_name


def create_safe_task(coro):
    async def wrapper():
        try:
            await coro
        except Exception:
            logger.exception("Background task crashed")

    return asyncio.create_task(wrapper())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Quiz Game Bot is running!")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your ID: {update.effective_user.id}")


# =========================
# ADD QUESTION
# =========================
async def add_question_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Only admin can use this command.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text("Send the question text:")
    return QUESTION


async def question_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["question"] = update.message.text.strip()
    await update.message.reply_text("Send option A:")
    return A


async def a_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["a"] = update.message.text.strip()
    await update.message.reply_text("Send option B:")
    return B


async def b_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["b"] = update.message.text.strip()
    await update.message.reply_text("Send option C:")
    return C


async def c_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["c"] = update.message.text.strip()
    await update.message.reply_text("Send option D:")
    return D


async def d_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["d"] = update.message.text.strip()
    await update.message.reply_text("Which option is correct? Send only A, B, C, or D")
    return CORRECT


async def correct_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    correct = update.message.text.strip().upper()

    if correct not in ["A", "B", "C", "D"]:
        await update.message.reply_text("Invalid answer. Send only A, B, C, or D.")
        return CORRECT

    add_question(
        context.user_data["question"],
        context.user_data["a"],
        context.user_data["b"],
        context.user_data["c"],
        context.user_data["d"],
        correct,
    )

    context.user_data.clear()
    await update.message.reply_text("Question added successfully ✅")
    return ConversationHandler.END


async def cancel_add_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# =========================
# GAME START
# =========================
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await update.message.reply_text("Use /startgame inside a group.")
        return

    if chat.id in active_games:
        await update.message.reply_text("A game is already running in this group.")
        return

    active_games[chat.id] = {
        "status": "joining",
        "players": {},
        "scores": {},
        "round": 0,
        "answers": {},
        "question_started_at": None,
        "correct": None,
        "question_id": None,
        "countdown_message_id": None,
    }

    keyboard = [[InlineKeyboardButton("🎮 Join Game", callback_data=f"join|{chat.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎮 New Quiz Game!\n\n"
        f"Rounds: {ROUNDS_PER_GAME}\n"
        f"Minimum players: {MIN_PLAYERS}\n"
        f"Join time: {JOIN_SECONDS} seconds\n\n"
        f"Press Join to play!",
        reply_markup=reply_markup,
    )

    create_safe_task(begin_game_after_join(chat.id, context))


async def begin_game_after_join(chat_id, context):
    await asyncio.sleep(JOIN_SECONDS)

    game = active_games.get(chat_id)
    if not game:
        return

    if len(game["players"]) < MIN_PLAYERS:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Not enough players. Need at least {MIN_PLAYERS} players."
        )
        active_games.pop(chat_id, None)
        return

    players_text = "\n".join(
        f"{i+1}. {player['name']}"
        for i, player in enumerate(game["players"].values())
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Players joined:\n\n{players_text}\n\nGame starting..."
    )

    await asyncio.sleep(2)
    await send_question(chat_id, context)


# =========================
# QUESTION FLOW
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
        await context.bot.send_message(chat_id=chat_id, text="No questions available.")
        active_games.pop(chat_id, None)
        return

    q_id, q_text, a, b, c, d, correct = question

    game["status"] = "question"
    game["question_id"] = q_id
    game["correct"] = correct
    game["answers"] = {}
    game["question_started_at"] = time.time()

    keyboard = [
        [
            InlineKeyboardButton(f"A) {a}", callback_data=f"ans|{chat_id}|{q_id}|A"),
            InlineKeyboardButton(f"B) {b}", callback_data=f"ans|{chat_id}|{q_id}|B"),
        ],
        [
            InlineKeyboardButton(f"C) {c}", callback_data=f"ans|{chat_id}|{q_id}|C"),
            InlineKeyboardButton(f"D) {d}", callback_data=f"ans|{chat_id}|{q_id}|D"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"Round {game['round']}/{ROUNDS_PER_GAME}\n\n"
            f"{q_text}\n\n"
            f"Choose your answer below."
        ),
        reply_markup=reply_markup,
    )

    countdown_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏳ Time left: {QUESTION_SECONDS}s"
    )
    game["countdown_message_id"] = countdown_msg.message_id

    create_safe_task(run_round_timer(chat_id, context, q_id))


async def run_round_timer(chat_id, context, q_id):
    for remaining in range(QUESTION_SECONDS - 1, -1, -1):
        await asyncio.sleep(1)

        game = active_games.get(chat_id)
        if not game:
            return

        if game["status"] != "question":
            return

        if game["question_id"] != q_id:
            return

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game["countdown_message_id"],
                text=f"⏳ Time left: {remaining}s"
            )
        except Exception as e:
            logger.warning("Countdown edit failed: %s", e)

    game = active_games.get(chat_id)
    if not game:
        return

    if game["status"] != "question":
        return

    if game["question_id"] != q_id:
        return

    game["status"] = "round_end"

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ Time's up!\nCorrect answer: {game['correct']}"
    )

    await send_round_leaderboard(chat_id, context)

    await asyncio.sleep(2)
    await send_question(chat_id, context)


async def send_round_leaderboard(chat_id, context):
    game = active_games.get(chat_id)
    if not game:
        return

    winners = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)

    if not winners:
        await context.bot.send_message(chat_id=chat_id, text="No points scored yet.")
        return

    text = f"📊 Leaderboard after round {game['round']}\n\n"
    for i, (user_id, points) in enumerate(winners[:10], start=1):
        name = game["players"].get(user_id, {}).get("name", str(user_id))
        text += f"{i}. {name} — {points} pts\n"

    await context.bot.send_message(chat_id=chat_id, text=text)


# =========================
# CALLBACKS
# =========================
async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data.split("|")

    now = time.time()
    last_click = user_last_click.get(user.id, 0)
    if now - last_click < SPAM_SECONDS:
        await query.answer("Too fast. Wait a moment.")
        return
    user_last_click[user.id] = now

    if data[0] == "join":
        chat_id = int(data[1])
        game = active_games.get(chat_id)

        if not game or game["status"] != "joining":
            await query.answer("Joining time is over.", show_alert=True)
            return

        if user.id in game["players"]:
            await query.answer("You already joined.", show_alert=True)
            return

        game["players"][user.id] = {
            "name": get_name(user),
            "username": user.username,
            "full_name": user.full_name,
        }
        game["scores"][user.id] = 0

        ensure_player(user.id, user.username, user.full_name)

        await query.answer("You joined the game!", show_alert=True)
        return

    if data[0] == "ans":
        chat_id = int(data[1])
        q_id = int(data[2])
        user_answer = data[3]

        game = active_games.get(chat_id)
        if not game:
            await query.answer("No active game.")
            return

        if game["status"] != "question":
            await query.answer("This round is closed.", show_alert=True)
            return

        if user.id not in game["players"]:
            await query.answer("You must join first.", show_alert=True)
            return

        if q_id != game["question_id"]:
            await query.answer("Old question.", show_alert=True)
            return

        if user.id in game["answers"]:
            await query.answer("You already answered.", show_alert=True)
            return

        elapsed = time.time() - game["question_started_at"]
        points = 0

        if user_answer == game["correct"]:
            points = CORRECT_POINTS
            if elapsed <= SPEED_BONUS_SECONDS:
                points += SPEED_BONUS_POINTS

            add_points(user.id, user.username, user.full_name, chat_id, points)
            game["scores"][user.id] = game["scores"].get(user.id, 0) + points

        game["answers"][user.id] = user_answer

        if points > 0:
            await query.answer(f"Correct! +{points} points")
        else:
            await query.answer("Wrong answer.")


# =========================
# LEADERBOARDS
# =========================
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_group_leaderboard(update.effective_chat.id)

    if not rows:
        await update.message.reply_text("No group scores yet.")
        return

    text = "🏆 Group Leaderboard\n\n"
    for i, r in enumerate(rows, start=1):
        name = f"@{r[1]}" if r[1] else r[0]
        text += f"{i}. {name} — {r[2]} pts\n"

    await update.message.reply_text(text)


async def global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_global_leaderboard()

    if not rows:
        await update.message.reply_text("No global scores yet.")
        return

    text = "🌍 Global Leaderboard\n\n"
    for i, r in enumerate(rows, start=1):
        name = f"@{r[1]}" if r[1] else r[0]
        text += f"{i}. {name} — {r[2]} pts\n"

    await update.message.reply_text(text)


# =========================
# END GAME
# =========================
async def end_game(chat_id, context):
    game = active_games.get(chat_id)
    if not game:
        return

    winners = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)

    if not winners:
        text = "Game ended. Nobody scored any points."
    else:
        text = "🏆 Final Winners\n\n"
        for i, (user_id, points) in enumerate(winners[:10], start=1):
            name = game["players"].get(user_id, {}).get("name", str(user_id))
            text += f"{i}. {name} — {points} pts\n"

    await context.bot.send_message(chat_id=chat_id, text=text)
    active_games.pop(chat_id, None)


# =========================
# MAIN
# =========================
def main():
    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()

    add_question_handler = ConversationHandler(
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(add_question_handler)
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("global", global_leaderboard))
    app.add_handler(CallbackQueryHandler(answer))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()