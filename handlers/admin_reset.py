# handlers/admin_reset.py

from contextlib import closing
from telegram.ext import ContextTypes
from database import get_conn
from .states import ADMIN_MENU


async def reset_all_time_leaderboard(query, context):
    """Resets all-time leaderboard: points, streaks, game stats for all players."""
    try:
        with closing(get_conn()) as conn, conn:
            conn.execute("""
                UPDATE players SET
                    total_points = 0,
                    games_played = 0,
                    games_won = 0,
                    duel_games_played = 0,
                    duel_games_won = 0,
                    correct_answers = 0,
                    wrong_answers = 0,
                    current_streak = 0,
                    best_streak = 0,
                    fastest_answer_time = NULL
            """)
            conn.execute("DELETE FROM player_points_history")

        await query.edit_message_text("✅ All-time leaderboard has been reset.")
    except Exception as e:
        await query.edit_message_text(f"❌ Error resetting leaderboard: {e}")
    return ADMIN_MENU


async def full_reset_all_data(query, context):
    """Full reset: clears all game history and player stats."""
    try:
        with closing(get_conn()) as conn, conn:
            conn.execute("DELETE FROM game_results")
            conn.execute("DELETE FROM games")
            conn.execute("DELETE FROM player_points_history")
            conn.execute("DELETE FROM group_points_history")
            conn.execute("""
                UPDATE players SET
                    total_points = 0,
                    games_played = 0,
                    games_won = 0,
                    duel_games_played = 0,
                    duel_games_won = 0,
                    correct_answers = 0,
                    wrong_answers = 0,
                    current_streak = 0,
                    best_streak = 0,
                    fastest_answer_time = NULL
            """)
            conn.execute("""
                UPDATE group_scores SET
                    total_points = 0,
                    games_played = 0,
                    games_won = 0,
                    correct_answers = 0,
                    wrong_answers = 0
            """)

        await query.edit_message_text("✅ All data has been fully reset.")
    except Exception as e:
        await query.edit_message_text(f"❌ Error during full reset: {e}")
    return ADMIN_MENU