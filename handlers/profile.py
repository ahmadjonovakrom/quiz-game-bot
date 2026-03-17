from telegram import Update
from telegram.ext import ContextTypes

from database import (
    ensure_player,
    get_top_players,
    get_player,
    get_player_rank,
)


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)

    player = get_player(user.id)
    rank = get_player_rank(user.id)

    if not player:
        await update.message.reply_text("No profile data yet.")
        return

    display_name = f"@{player['username']}" if player["username"] else player["full_name"]
    fastest = player["fastest_answer_time"]

    fastest_text = f"{fastest:.2f}s" if fastest is not None else "—"

    text = (
        "👤 Player Profile\n\n"
        f"Name: {display_name}\n"
        f"Games played: {player['games_played']}\n"
        f"Games won: {player['games_won']}\n"
        f"Correct answers: {player['correct_answers']}\n"
        f"Wrong answers: {player['wrong_answers']}\n"
        f"Best streak: {player['best_streak']}\n"
        f"Total points: {player['total_points']}\n"
        f"Fastest answer: {fastest_text}\n"
        f"Global rank: #{rank if rank else '-'}"
    )

    await update.message.reply_text(text)


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_top_players(limit=10)

    if not rows:
        await update.message.reply_text("No scores yet.")
        return

    text = "🏆 Leaderboard\n\n"

    for i, row in enumerate(rows, start=1):
        name = f"@{row['username']}" if row["username"] else row["full_name"]
        text += f"{i}. {name} — {row['total_points']} 🍋\n"

    await update.message.reply_text(text)


async def global_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_top_players(limit=10)

    if not rows:
        await update.message.reply_text("No global scores yet.")
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🌍 Global Leaderboard\n\n"

    for i, row in enumerate(rows, start=1):
        name = f"@{row['username']}" if row["username"] else row["full_name"]
        prefix = medals[i - 1] if i <= 3 else f"{i}."
        text += f"{prefix} {name} — {row['total_points']} 🍋\n"

    await update.message.reply_text(text)