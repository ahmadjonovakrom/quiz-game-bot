import logging
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

from utils.shuffle import shuffle_question
from config import (
    DEFAULT_QUESTIONS_PER_GAME,
    DEFAULT_CATEGORY,
)
from database import (
    get_random_question,
    ensure_player,
    ensure_chat,
    ensure_group_player,
    has_played_daily_quiz,
    record_daily_quiz_attempt,
)
from utils.helpers import safe_delete_message
from utils.keyboards import game_setup_questions_keyboard
from services.game_service import (
    active_games,
    poll_map,
    get_game_lock,
    clear_game,
    create_new_game_data,
    get_existing_game_message,
    add_player_to_game,
    get_join_remaining_seconds,
)
from handlers.game_setup import (
    load_dynamic_settings,
    refresh_join_message,
    game_setup_callback_handler,
    has_active_game,
)

logger = logging.getLogger(__name__)


def row_value(row, key, default=None):
    if row is None:
        return default
    try:
        value = row[key]
        return default if value is None else value
    except Exception:
        return default


def get_question_points(difficulty: str) -> int:
    settings = load_dynamic_settings()
    points = settings["POINTS"]

    if not difficulty:
        return points["easy"]

    return points.get(str(difficulty).lower(), points["easy"])


def format_question_text(question: str, points: int) -> str:
    return f"{question}\n🍋 +{points}"


async def _send_play_again_setup_message(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    title: str = "🎮 Game Setup",
):
    try:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=f"{title}\n\nStep 1 of 2 — Choose number of questions",
            reply_markup=game_setup_questions_keyboard(),
        )
    except Exception as e:
        logger.exception("Failed to send play again setup message: %s", e)
        return None


async def daily_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        settings = load_dynamic_settings()
        question_seconds = settings.get("QUESTION_SECONDS", 60)
    except Exception:
        logger.exception("Failed to load dynamic settings")
        await update.message.reply_text("❌ Internal error loading settings.")
        return

    logger.info("DAILY QUIZ COMMAND RECEIVED")

    user = update.effective_user
    chat = update.effective_chat
    today = str(date.today())

    if not (update.message and user and chat):
        logger.warning("Missing message, user, or chat in daily quiz.")
        return

    try:
        ensure_chat(chat)
    except Exception:
        logger.exception("Failed to ensure chat in database")
        await update.message.reply_text("❌ Could not validate chat.")
        return

    try:
        already_played = has_played_daily_quiz(user.id, today)
    except Exception:
        logger.exception("Failed to check if user played daily quiz")
        await update.message.reply_text("❌ Could not check daily quiz status.")
        return

    if already_played:
        await update.message.reply_text("You already played today's daily quiz.")
        return

    try:
        ensure_player(user)
    except Exception:
        logger.exception("Failed to ensure player in DB")
        await update.message.reply_text("❌ Could not register player.")
        return

    try:
        question = get_random_question()
        logger.info(
            "Daily question fetched: %s",
            dict(question) if question else None,
        )
    except Exception:
        logger.exception("Failed to fetch daily question")
        await update.message.reply_text("❌ Failed to load daily question.")
        return

    if not question:
        await update.message.reply_text("No questions available.")
        return

    try:
        q_id = question.get("id") if hasattr(question, "get") else question["id"]
        q_text = question.get("question_text") if hasattr(question, "get") else question["question_text"]
        difficulty = row_value(question, "difficulty", "easy")
        points = 450

        if not q_id or not q_text:
            logger.error("Question fetched missing ID or text")
            await update.message.reply_text("Question data incomplete.")
            return

        options, correct_index = shuffle_question(question)

        if correct_index not in range(len(options)):
            await update.message.reply_text(
                "This daily question has an invalid correct answer."
            )
            logger.error(
                "Invalid correct option index: %s for options: %s",
                correct_index,
                options,
            )
            return

        msg = await context.bot.send_poll(
            chat_id=chat.id,
            question=format_question_text(q_text, points),
            options=options,
            type="quiz",
            correct_option_id=correct_index,
            is_anonymous=False,
            open_period=int(question_seconds),
        )
    except Exception:
        logger.exception("Failed to send daily quiz poll for user %s", user.id)
        await update.message.reply_text(
            "Failed to send the daily quiz.\nPlease try again."
        )
        return

    try:
        poll_map[msg.poll.id] = {
            "chat_id": chat.id,
            "round": "daily",
            "daily_user_id": user.id,
            "daily_date": today,
            "correct_index": correct_index,
            "question_id": q_id,
            "difficulty": difficulty,
            "points": points,
        }
        record_daily_quiz_attempt(user.id, today)
    except Exception:
        logger.exception("Failed to record daily quiz attempt (user.id=%s)", user.id)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = getattr(update, "callback_query", None)
    if not (query and query.message):
        logger.warning("No callback_query or callback_query.message in button_handler.")
        return

    logger.info("BUTTON CALLBACK: %s", getattr(query, "data", None))
    data = query.data or ""

    if (
        data.startswith("setup_")
        or data in ("menu_back", "menu_main")
        or data.startswith("setup_back_to_results:")
    ):
        handled = await game_setup_callback_handler(update, context)
        if handled is True:
            return

    if data.startswith("duel_rematch:"):
        chat_id = query.message.chat.id
        user = query.from_user

        try:
            _, p1_id, p2_id = data.split(":")
            allowed_players = {int(p1_id), int(p2_id)}
        except Exception:
            await query.answer("Invalid duel rematch.", show_alert=True)
            logger.error("Malformed duel_rematch callback: %s", data)
            return

        if user.id not in allowed_players:
            await query.answer(
                "This rematch is only for previous duel players.",
                show_alert=True,
            )
            return

        await query.answer()

        lock = get_game_lock(chat_id)
        async with lock:
            if has_active_game(chat_id):
                existing_game = active_games.get(chat_id)
                await query.answer(
                    get_existing_game_message(existing_game),
                    show_alert=True,
                )
                return

            game = create_new_game_data(
                started_by=user.id,
                questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
                category="mixed",
                difficulty="mixed",
            )

            game.update({
                "chat_id": chat_id,
                "mode": "duel",
                "min_players": 2,
                "max_players": 2,
                "category": "mixed",
                "difficulty": "mixed",
                "allowed_players": allowed_players,
            })

            add_player_to_game(game, user)
            active_games[chat_id] = game

        try:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text="⚔️ Duel Setup\n\n"
                     "Step 1 of 1 — Choose number of questions\n\n"
                     "• Mode: 1 vs 1\n"
                     "• Category: Mixed\n"
                     "• Difficulty: Mixed",
                reply_markup=game_setup_questions_keyboard(),
            )
        except Exception:
            logger.exception("Failed to send duel rematch setup message.")
            return

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if game and msg:
                game["setup_message_id"] = msg.message_id

        return

    if data == "duel_new_game":
        chat_id = query.message.chat.id
        user = query.from_user

        await query.answer()
        lock = get_game_lock(chat_id)
        async with lock:
            if has_active_game(chat_id):
                existing_game = active_games.get(chat_id)
                await query.answer(
                    get_existing_game_message(existing_game),
                    show_alert=True,
                )
                return

            game = create_new_game_data(
                started_by=user.id,
                questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
                category="mixed",
                difficulty="mixed",
            )
            game.update({
                "chat_id": chat_id,
                "mode": "duel",
                "min_players": 2,
                "max_players": 2,
                "category": "mixed",
                "difficulty": "mixed",
                "allowed_players": None,
            })
            add_player_to_game(game, user)
            active_games[chat_id] = game

        try:
            await query.edit_message_text(
                "⚔️ Duel Setup\n\n"
                "Step 1 of 1 — Choose number of questions\n\n"
                "• Mode: 1 vs 1\n"
                "• Category: Mixed\n"
                "• Difficulty: Mixed",
                reply_markup=game_setup_questions_keyboard(),
            )
        except Exception:
            logger.exception("Failed to edit duel setup message.")
        return

    if data.startswith("results_play_again:"):
        chat_id = query.message.chat.id
        user = query.from_user

        try:
            int(data.split(":", maxsplit=1)[1])
        except (IndexError, ValueError):
            await query.answer("Invalid game.", show_alert=True)
            return

        await query.answer()

        lock = get_game_lock(chat_id)
        async with lock:
            if has_active_game(chat_id):
                existing_game = active_games.get(chat_id)
                await query.answer(
                    get_existing_game_message(existing_game),
                    show_alert=True,
                )
                return

            old_game = active_games.get(chat_id)
            old_setup_message_id = old_game.get("setup_message_id") if old_game else None
            old_join_message_id = old_game.get("join_message_id") if old_game else None

            await clear_game(context, chat_id)

            game = create_new_game_data(
                started_by=user.id,
                questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
                category=DEFAULT_CATEGORY,
                difficulty="mixed",
            )
            game.update({
                "chat_id": chat_id,
                "mode": "solo",
                "results_message_id": query.message.message_id,
                "setup_message_id": None,
                "join_message_id": None,
            })
            add_player_to_game(game, user)
            active_games[chat_id] = game

        if old_setup_message_id:
            try:
                await safe_delete_message(context.bot, chat_id, old_setup_message_id)
            except Exception:
                logger.exception("Failed to delete old setup message %s", old_setup_message_id)

        if old_join_message_id and old_join_message_id != old_setup_message_id:
            try:
                await safe_delete_message(context.bot, chat_id, old_join_message_id)
            except Exception:
                logger.exception("Failed to delete old join message %s", old_join_message_id)

        setup_message = await _send_play_again_setup_message(chat_id, context)
        if setup_message is None:
            lock = get_game_lock(chat_id)
            async with lock:
                if chat_id in active_games:
                    del active_games[chat_id]
            return

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if game:
                game["setup_message_id"] = setup_message.message_id
        return

    parts = data.split("|")
    if parts[0] == "join":
        try:
            chat_id = int(parts[1])
        except (IndexError, ValueError):
            await query.answer("Invalid join request.")
            return

        try:
            if query.message.chat:
                ensure_chat(query.message.chat)
        except Exception:
            logger.exception("Failed to ensure chat on join")

        # These are set inside the lock and read after.
        join_message_id = None
        should_start_duel = False
        duel_intro_text = None

        user = query.from_user
        if user is None:
            await query.answer("Missing user.")
            return

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)

            if not game:
                await query.answer("No active game")
                return

            status = game.get("status", "joining")
            if status != "joining":
                await query.answer("Joining closed")
                return

            player_dict = game.get("players", {})

            if game.get("mode") == "duel":
                allowed_players = game.get("allowed_players")

                if allowed_players and user.id not in allowed_players:
                    await query.answer(
                        "This rematch is only for previous duel players.",
                        show_alert=True,
                    )
                    return

                if len(player_dict) >= 2:
                    await query.answer("This duel already has 2 players.")
                    return

            if game.get("mode") == "rematch":
                allowed_players = game.get("allowed_players") or set()
                if user.id not in allowed_players:
                    await query.answer(
                        "This rematch is only for players from the previous match.",
                        show_alert=True,
                    )
                    return

            added = add_player_to_game(game, user)

            if not added:
                if user.id in player_dict:
                    await query.answer("Already joined")
                else:
                    if game.get("mode") == "duel":
                        await query.answer("This duel already has 2 players.")
                    elif game.get("mode") == "rematch":
                        await query.answer(
                            "This rematch is only for players from the previous match.",
                            show_alert=True,
                        )
                    else:
                        await query.answer("Unable to join.")
                return

            # FIX: check and set status to "running" INSIDE the lock so that
            # a second rapid join callback cannot also see 2 players and
            # trigger send_question twice.
            if game.get("mode") == "duel" and len(game["players"]) == 2:
                # Guard: only trigger duel start once
                if game.get("duel_start_triggered"):
                    await query.answer("Joined!")
                    return
                game["duel_start_triggered"] = True
                game["status"] = "running"
                join_message_id = game.get("join_message_id")
                should_start_duel = True

                players = list(game["players"].items())
                user1_id, p1 = players[0]
                user2_id, p2 = players[1]

                def display_name(player_data):
                    return (
                        player_data.get("full_name")
                        or player_data.get("first_name")
                        or (
                            f"@{player_data.get('username')}"
                            if player_data.get("username")
                            else None
                        )
                        or "Player"
                    )

                duel_intro_text = (
                    "⚔️ DUEL START 🍋\n\n"
                    "🔥 Battle begins!\n\n"
                    f"🆚 {display_name(p1)} vs {display_name(p2)}\n\n"
                    "⚡ First question coming..."
                )

        # DB calls outside the lock — safe because they are per-user
        try:
            ensure_player(user)
        except Exception:
            logger.exception("Failed to ensure player on join")

        if chat_id < 0:
            try:
                ensure_group_player(chat_id, user)
            except Exception:
                logger.exception("Failed to ensure group player in join callback")

        if should_start_duel:
            try:
                await safe_delete_message(context.bot, chat_id, join_message_id)
            except Exception:
                logger.warning("Failed to delete join message %s in chat %s", join_message_id, chat_id)

            try:
                await context.bot.send_message(
                    chat_id,
                    duel_intro_text or "⚔️ Duel started!\nGet ready for the first question.",
                )
            except Exception:
                logger.exception("Failed to send duel intro message to chat %s", chat_id)
                return

            try:
                from handlers.game_play import send_question
                await send_question(chat_id, context)
            except Exception:
                logger.exception("Failed to send first question for duel in chat %s", chat_id)
            return

        try:
            game = active_games.get(chat_id)
            shown_remaining = None

            if game and game.get("status") == "joining":
                actual_remaining = get_join_remaining_seconds(game)

                if actual_remaining > 10:
                    shown_remaining = ((actual_remaining + 9) // 10) * 10
                else:
                    shown_remaining = actual_remaining

            await refresh_join_message(context, chat_id, shown_remaining)
        except Exception:
            logger.exception("Failed to refresh join message for chat %s", chat_id)

        await query.answer("Joined!")
        return

    try:
        await query.answer()
    except Exception:
        logger.debug("query.answer() failed (likely already answered).")