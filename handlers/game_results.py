import html
import logging

from telegram import Update
from telegram.ext import ContextTypes

from database import finish_game
from utils.helpers import safe_delete_message, is_game_controller
from utils.keyboards import final_results_keyboard, FINAL_RESULTS_PAGE_SIZE
from services.game_service import (
    active_games,
    poll_map,
    get_game_lock,
    cleanup_game_lock,
)

logger = logging.getLogger(__name__)


def make_clickable_name(row):
    raw_name = (
        row.get("full_name")
        or row.get("name")
        or row.get("username")
        or "Unknown"
    )
    safe_name = html.escape(str(raw_name))
    user_id = row.get("user_id")

    if user_id:
        return f'<a href="tg://user?id={user_id}">{safe_name}</a>'

    return safe_name


def format_final_results_page(results, page=1):
    total = len(results)
    total_pages = max(1, (total + FINAL_RESULTS_PAGE_SIZE - 1) // FINAL_RESULTS_PAGE_SIZE)

    page = max(1, min(page, total_pages))
    start = (page - 1) * FINAL_RESULTS_PAGE_SIZE
    end = start + FINAL_RESULTS_PAGE_SIZE
    chunk = results[start:end]
    has_next = page < total_pages

    lines = ["🍋 ENGLISH LEMON RESULTS", "", "🏆 Final Leaderboard:"]

    for index, row in enumerate(chunk, start=start + 1):
        name = make_clickable_name(row)
        points = row.get("points", 0)

        if index == 1:
            prefix = "🥇"
        elif index == 2:
            prefix = "🥈"
        elif index == 3:
            prefix = "🥉"
        else:
            prefix = f"{index}."

        lines.append(f"{prefix} {name} — {points} 🍋")

    if results:
        mvp = max(results, key=lambda x: x.get("points", 0))

        def accuracy_value(row):
            correct = row.get("correct_answers", 0)
            wrong = row.get("wrong_answers", 0)
            total_answers = correct + wrong

            if total_answers == 0:
                return -1

            return (correct / total_answers) * 100

        valid_players = [
            r for r in results
            if (r.get("correct_answers", 0) + r.get("wrong_answers", 0)) > 0
        ]

        accuracy_king = None
        if valid_players:
            accuracy_king = max(
                valid_players,
                key=lambda x: (
                    accuracy_value(x),
                    x.get("correct_answers", 0),
                ),
            )

        mvp_name = make_clickable_name(mvp)

        lines.append("")
        lines.append(f"👑 MVP: {mvp_name}")

        if not accuracy_king:
            lines.append("🎯 Accuracy Champion: No answers yet")
        else:
            accuracy_name = make_clickable_name(accuracy_king)
            accuracy_percent = round(accuracy_value(accuracy_king))
            lines.append(f"🎯 Accuracy Champion: {accuracy_name} ({accuracy_percent}%)")

    return "\n".join(lines), has_next


async def show_saved_results(query, context, result_id: int):
    all_results = context.bot_data.get("final_results_pages", {}).get(result_id)
    if not all_results:
        await query.edit_message_text("Results not available.")
        return True

    text, has_next = format_final_results_page(all_results, page=1)
    markup = final_results_keyboard(result_id, 1, has_next)

    try:
        await query.edit_message_text(
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
    except Exception:
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
        )

    return True


async def final_results_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, game_id_str, page_str = query.data.split(":")
        game_id = int(game_id_str)
        page = int(page_str)
    except Exception:
        await query.answer("Invalid page.", show_alert=True)
        return

    all_results = context.bot_data.get("final_results_pages", {}).get(game_id)
    if not all_results:
        await query.edit_message_text("Final results are no longer available.")
        return

    text, has_next = format_final_results_page(all_results, page=page)
    markup = final_results_keyboard(game_id, page, has_next)

    try:
        await query.edit_message_text(
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
    except Exception:
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
        )


async def end_game(chat_id, context):
    logger.warning("END GAME: %s", chat_id)

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game:
            return

        poll_id = game.get("current_poll_id")
        db_game_id = game.get("db_game_id")
        players = game.get("players", {})
        total_rounds = game.get("round", 0)

        if poll_id:
            poll_map.pop(poll_id, None)

        normalized_results = []

        for user_id, player_data in players.items():
            result_row = {
                "user_id": user_id,
                "name": player_data.get("name"),
                "username": player_data.get("username"),
                "full_name": player_data.get("full_name"),
                "points": game.get("scores", {}).get(user_id, 0),
                "correct_answers": game.get("correct_counts", {}).get(user_id, 0),
                "wrong_answers": game.get("wrong_counts", {}).get(user_id, 0),
            }
            normalized_results.append(result_row)

        normalized_results.sort(
            key=lambda x: (
                -x.get("points", 0),
                -x.get("correct_answers", 0),
                x.get("wrong_answers", 0),
                (x.get("full_name") or x.get("name") or x.get("username") or "").lower(),
            )
        )

        winner_user_id = normalized_results[0]["user_id"] if normalized_results else None

        active_games.pop(chat_id, None)
        cleanup_game_lock(chat_id)

    if db_game_id:
        try:
            finish_game(
                game_id=db_game_id,
                winner_user_id=winner_user_id,
                total_players=len(players),
                total_rounds=total_rounds,
                status="finished",
            )
        except Exception:
            logger.exception("Failed to finish game %s", db_game_id)

    if not normalized_results:
        await context.bot.send_message(chat_id, "Game ended. No results available.")
        return

    result_id = db_game_id or chat_id
    context.bot_data.setdefault("final_results_pages", {})[result_id] = normalized_results

    text, has_next = format_final_results_page(normalized_results, page=1)
    markup = final_results_keyboard(result_id, 1, has_next)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=markup,
        parse_mode="HTML",
    )


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("STOP GAME COMMAND RECEIVED")

    chat = update.effective_chat
    user = update.effective_user

    if not user:
        await update.message.reply_text("Only the game starter or a group admin can stop this game.")
        return

    game = active_games.get(chat.id)
    allowed = await is_game_controller(context, chat.id, user.id, game)

    if not allowed:
        await update.message.reply_text("Only the game starter or a group admin can stop this game.")
        return

    lock = get_game_lock(chat.id)
    async with lock:
        if chat.id not in active_games:
            await update.message.reply_text("No game is currently running.")
            return

        game = active_games.get(chat.id)
        poll_id = game.get("current_poll_id")
        join_message_id = game.get("join_message_id")
        db_game_id = game.get("db_game_id")
        total_players = len(game.get("players", {}))
        total_rounds = game.get("round", 0)

        if poll_id:
            poll_map.pop(poll_id, None)

        active_games.pop(chat.id, None)
        cleanup_game_lock(chat.id)

    await safe_delete_message(context.bot, chat.id, join_message_id)

    if db_game_id:
        try:
            finish_game(
                game_id=db_game_id,
                winner_user_id=None,
                total_players=total_players,
                total_rounds=total_rounds,
                status="stopped",
            )
        except Exception:
            logger.exception("Failed to mark stopped game in database for chat %s", chat.id)

    await update.message.reply_text("Game stopped.")