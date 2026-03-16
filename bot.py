import asyncio
import time
import random

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
    get_question_by_id,
    ensure_player,
    add_points,
    get_group_leaderboard,
    get_global_leaderboard,
)

QUESTION, A, B, C, D, CORRECT = range(6)

active_games = {}

ROUNDS_PER_GAME = 5


def get_name(user):
    if user.username:
        return f"@{user.username}"
    return user.full_name


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Quiz Game Bot is running!")


# GAME START
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type == "private":
        await update.message.reply_text("Use /startgame inside a group.")
        return

    if chat.id in active_games:
        await update.message.reply_text("A game is already running.")
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
    }

    keyboard = [[InlineKeyboardButton("🎮 Join Game", callback_data=f"join|{chat.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎮 **New Quiz Game!**\n\n"
        f"Rounds: {ROUNDS_PER_GAME}\n"
        f"Minimum players: {MIN_PLAYERS}\n"
        f"Join time: {JOIN_SECONDS}s\n\n"
        f"Press Join to play!",
        reply_markup=reply_markup,
    )

    asyncio.create_task(begin_game_after_join(chat.id, context))


# AFTER JOIN TIMER
async def begin_game_after_join(chat_id, context):
    await asyncio.sleep(JOIN_SECONDS)

    game = active_games.get(chat_id)
    if not game:
        return

    if len(game["players"]) < MIN_PLAYERS:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Not enough players. Need {MIN_PLAYERS}."
        )
        active_games.pop(chat_id, None)
        return

    players_text = "\n".join(
        f"{i+1}. {p['name']}"
        for i, p in enumerate(game["players"].values())
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🎮 Players Joined:\n\n{players_text}\n\nGame starting..."
    )

    await asyncio.sleep(3)

    await send_question(chat_id, context)


# SEND QUESTION
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
        await context.bot.send_message(chat_id, "No questions available.")
        return

    q_id, q_text, a, b, c, d, correct = question

    game["question_id"] = q_id
    game["correct"] = correct
    game["answers"] = {}
    game["question_started_at"] = time.time()

    keyboard = [
        [
            InlineKeyboardButton("A", callback_data=f"ans|{chat_id}|{q_id}|A"),
            InlineKeyboardButton("B", callback_data=f"ans|{chat_id}|{q_id}|B"),
        ],
        [
            InlineKeyboardButton("C", callback_data=f"ans|{chat_id}|{q_id}|C"),
            InlineKeyboardButton("D", callback_data=f"ans|{chat_id}|{q_id}|D"),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"🧠 **Round {game['round']}/{ROUNDS_PER_GAME}**\n\n"
        f"{q_text}\n\n"
        f"A) {a}\n"
        f"B) {b}\n"
        f"C) {c}\n"
        f"D) {d}\n\n"
        f"⏱ {QUESTION_SECONDS} seconds"
    )

    await context.bot.send_message(chat_id, message, reply_markup=reply_markup)

    asyncio.create_task(finish_round(chat_id, context))


# ROUND END
async def finish_round(chat_id, context):
    await asyncio.sleep(QUESTION_SECONDS)

    game = active_games.get(chat_id)
    if not game:
        return

    correct = game["correct"]

    await context.bot.send_message(
        chat_id,
        f"⏰ Time's up!\nCorrect answer: {correct}"
    )

    await asyncio.sleep(2)

    await send_question(chat_id, context)


# ANSWER HANDLER
async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")

    # JOIN BUTTON
    if data[0] == "join":
        chat_id = int(data[1])
        game = active_games.get(chat_id)

        user = query.from_user

        if user.id in game["players"]:
            await query.answer("You already joined.", show_alert=True)
            return

        game["players"][user.id] = {
            "name": get_name(user),
            "username": user.username,
            "full_name": user.full_name,
        }

        ensure_player(user.id, user.username, user.full_name)

        await query.answer("You joined the game!", show_alert=True)
        return

    # ANSWERS
    if data[0] == "ans":
        chat_id = int(data[1])
        q_id = int(data[2])
        user_answer = data[3]

        game = active_games.get(chat_id)
        user = query.from_user

        if user.id in game["answers"]:
            await query.answer("Already answered.")
            return

        elapsed = time.time() - game["question_started_at"]

        points = 0

        if user_answer == game["correct"]:
            points = CORRECT_POINTS

            if elapsed <= SPEED_BONUS_SECONDS:
                points += SPEED_BONUS_POINTS

            add_points(
                user.id,
                user.username,
                user.full_name,
                chat_id,
                points
            )

            game["scores"][user.id] = game["scores"].get(user.id, 0) + points

        game["answers"][user.id] = True

        await query.answer(f"+{points} points")


# END GAME
async def end_game(chat_id, context):
    game = active_games.get(chat_id)

    winners = sorted(
        game["scores"].items(),
        key=lambda x: x[1],
        reverse=True
    )

    text = "🏆 **Final Winners**\n\n"

    for i, (user_id, points) in enumerate(winners[:5]):
        name = game["players"][user_id]["name"]
        text += f"{i+1}. {name} — {points} pts\n"

    await context.bot.send_message(chat_id, text)

    active_games.pop(chat_id)


# LEADERBOARD
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_group_leaderboard(update.effective_chat.id)

    text = "🏆 Group Leaderboard\n\n"

    for i, r in enumerate(rows):
        name = f"@{r[1]}" if r[1] else r[0]
        text += f"{i+1}. {name} — {r[2]} pts\n"

    await update.message.reply_text(text)


async def global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_global_leaderboard()

    text = "🌍 Global Leaderboard\n\n"

    for i, r in enumerate(rows):
        name = f"@{r[1]}" if r[1] else r[0]
        text += f"{i+1}. {name} — {r[2]} pts\n"

    await update.message.reply_text(text)


def main():
    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("global", global_leaderboard))
    app.add_handler(CallbackQueryHandler(answer))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()