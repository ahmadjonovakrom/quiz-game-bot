from telegram import Update
from telegram.ext import ContextTypes

from database import (
    ensure_player,
    get_group_leaderboard,
    get_global_leaderboard,
    get_player_profile,
)


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


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_group_leaderboard(update.effective_chat.id)

    if not rows:
        await update.message.reply_text("No scores yet.")
        return

    text = "🏆 Leaderboard\n\n"

    for i, r in enumerate(rows, start=1):
        name = f"@{r[1]}" if r[1] else r[0]
        text += f"{i}. {name} — {r[2]} 🍋\n"

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
        text += f"{prefix} {name} — {row[2]} 🍋\n"

    await update.message.reply_text(text)