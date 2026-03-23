import asyncio
import logging
from datetime import date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.shuffle import shuffle_question
from config import (
    CORRECT_POINTS,
    DEFAULT_QUESTIONS_PER_GAME,
    ALLOWED_QUESTION_COUNTS,
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
)
from database import (
    get_random_question,
    ensure_player,
    ensure_user,
    ensure_chat,
    ensure_group_player,
    add_points,
    add_group_points,
    record_correct_answer,
    record_group_correct_answer,
    record_group_wrong_answer,
    record_wrong_answer,
    increment_games_played,
    increment_group_games_played,
    increment_games_won,
    increment_group_games_won,
    create_game,
    finish_game,
    record_game_result,
    has_played_daily_quiz,
    record_daily_quiz_attempt,
    get_game_settings,
    has_claimed_group_bonus,
)
from handlers.profile import profile, leaderboard
from handlers.group_bonus import try_give_group_bonus
from utils.helpers import (
    safe_task,
    safe_delete_message,
    build_join_text,
    is_admin,
    is_group_admin,
)
from utils.keyboards import (
    main_menu_keyboard,
    game_setup_questions_keyboard,
    game_setup_categories_keyboard,
    game_setup_confirm_keyboard,
    final_results_keyboard,
    FINAL_RESULTS_PAGE_SIZE,
)
from services.game_service import (
    active_games,
    poll_map,
    get_game_lock,
    cleanup_game_lock,
    clear_game,
    create_new_game_data,
    get_existing_game_message,
    get_unused_question,
    add_player_to_game,
    mark_game_joining,
    start_next_round,
    prepare_round_state,
    apply_poll_answer,
)

logger = logging.getLogger(__name__)


def load_dynamic_settings():
    settings = get_game_settings()
    return {
        "MIN_PLAYERS": settings["min_players"],
        "JOIN_SECONDS": settings["join_seconds"],
        "QUESTION_SECONDS": settings["question_seconds"],
        "SPEED_BONUS_SECONDS": settings["speed_bonus_seconds"],
        "SPEED_BONUS_POINTS": settings["speed_bonus_points"],
        "POINTS": settings["points"],
    }


def has_active_game(chat_id: int) -> bool:
    game = active_games.get(chat_id)
    if not game:
        return False
    return game.get("status") in ("setup", "joining", "running")


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
        name = (
            row.get("full_name")
            or row.get("name")
            or row.get("username")
            or "Unknown"
        )
        points = row.get("points", 0)

        if index == 1:
            prefix = "🥇"
        elif index == 2:
            prefix = "🥈"
        elif index == 3:
            prefix = "🥉"
        else:
            prefix = f"{index}."

        lines.append(f"{prefix} {name} — {points}🍋")

    if results:
        mvp = max(results, key=lambda x: x.get("points", 0))

        def accuracy_value(row):
            correct = row.get("correct_answers", 0)
            wrong = row.get("wrong_answers", 0)
            total_answers = correct + wrong

            if total_answers == 0:
                return -1

            return (correct / total_answers) * 100

        accuracy_king = max(
            results,
            key=lambda x: (
                accuracy_value(x),
                x.get("correct_answers", 0),
            ),
        )

        mvp_name = (
            mvp.get("full_name")
            or mvp.get("name")
            or mvp.get("username")
            or "Unknown"
        )

        accuracy_name = (
            accuracy_king.get("full_name")
            or accuracy_king.get("name")
            or accuracy_king.get("username")
            or "Unknown"
        )

        accuracy_score = accuracy_value(accuracy_king)

        lines.append("")
        lines.append(f"👑 MVP: {mvp_name}")

        if accuracy_score < 0:
            lines.append("🎯 Accuracy Champion: No answers yet")
        else:
            accuracy_percent = int(accuracy_score)
            lines.append(f"🎯 Accuracy Champion: {accuracy_name} ({accuracy_percent}%)")



    return "\n".join(lines), has_next


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


CATEGORY_LABELS = {
    "mixed": "Mixed",
    "vocabulary": "Vocabulary",
    "grammar": "Grammar",
    "idioms_phrases": "Idioms & Phrases",
    "synonyms": "Synonyms",
    "collocations": "Collocations",
}


def row_value(row, key, default=None):
    if row is None:
        return default
    try:
        value = row[key]
        return default if value is None else value
    except Exception:
        return default


def format_category_name(category: str) -> str:
    return CATEGORY_LABELS.get(str(category).lower(), str(category).replace("_", " ").title())


def get_main_menu_keyboard():
    return main_menu_keyboard()


def get_question_count_keyboard(back_callback: str = "menu_main"):
    return game_setup_questions_keyboard(back_callback)


def get_category_keyboard():
    return game_setup_categories_keyboard()


def get_setup_confirmation_keyboard():
    return game_setup_confirm_keyboard()


def get_join_keyboard(chat_id: int):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Join", callback_data=f"join|{chat_id}")]]
    )


def format_setup_step_1_text() -> str:
    return (
        "🎮 Game Setup\n\n"
        "Step 1 of 2 — Choose number of questions"
    )


def format_setup_step_2_text(selected_count: int) -> str:
    return (
        "🎮 Game Setup\n\n"
        "Step 2 of 2 — Choose category\n\n"
        f"✅ Questions: {selected_count}"
    )


def format_setup_summary(question_count: int, category: str) -> str:
    settings = load_dynamic_settings()
    points = settings["POINTS"]

    return (
        "🎮 Game Setup\n\n"
        "✅ Ready to Start\n\n"
        "📋 Setup:\n"
        f"• Questions: {question_count}\n"
        f"• Category: {format_category_name(category)}\n"
        "• Difficulty: Mixed\n\n"
        "🍋 Rewards:\n"
        f"• Easy: +{points['easy']}\n"
        f"• Medium: +{points['medium']}\n"
        f"• Hard: +{points['hard']}\n\n"
        "🚀 Press Start when you're ready"
    )


def get_question_points(difficulty: str) -> int:
    settings = load_dynamic_settings()
    points = settings["POINTS"]

    if not difficulty:
        return points["easy"]
    return points.get(str(difficulty).lower(), points["easy"])


def format_question_text(question: str, points: int) -> str:
    return f"{question}\n🍋 +{points}"


async def refresh_join_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    settings = load_dynamic_settings()
    join_seconds = settings["JOIN_SECONDS"]

    game = active_games.get(chat_id)
    if not game or game.get("status") != "joining":
        return

    join_message_id = game.get("join_message_id")
    if not join_message_id:
        return

    display_remaining = game.get("display_remaining", join_seconds)
    blink = game.get("display_blink", False)

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=join_message_id,
            text=build_join_text(game, display_remaining, blink=blink),
            reply_markup=get_join_keyboard(chat_id),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Failed to refresh join message in chat %s: %s", chat_id, e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("START COMMAND RECEIVED")

    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if user:
        ensure_user(user)
        ensure_player(user)
    if chat:
        ensure_chat(chat)

    await message.reply_text(
        "Welcome to English Lemon !\n\n"
        "Practice vocabulary, play quiz games, and climb the leaderboard.",
        reply_markup=get_main_menu_keyboard(),
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.warning("MENU CALLBACK: %s", query.data)
    await query.answer()

    data = query.data
    back_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
    )

    if data.startswith("results_play_again:"):
        try:
            _, game_id_str = data.split(":")
            source_game_id = int(game_id_str)
        except Exception:
            await query.answer("Error.", show_alert=True)
            return

        chat_id = query.message.chat.id

        game = create_new_game_data(
            started_by=query.from_user.id,
            questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
            category=DEFAULT_CATEGORY,
            difficulty="mixed",
        )

        game["status"] = "setup"
        game["questions_per_game"] = None

        # use chat_id for reliable return path
        game["return_to_results"] = source_game_id

        add_player_to_game(game, query.from_user)
        active_games[chat_id] = game

        await query.edit_message_text(
            format_setup_step_1_text(),
            reply_markup=get_question_count_keyboard(
                back_callback=f"setup_back_to_results:{source_game_id}"
            ),
        )
        return

    if data == "menu_play":
        if query.message.chat.type in ("group", "supergroup"):
            allowed = is_admin(query.from_user.id) or await is_group_admin(
                context,
                query.message.chat.id,
                query.from_user.id,
            )

            if not allowed:
                await query.edit_message_text(
                    "❌ Admin only.\n\nOnly a group admin can start a quiz game.",
                    reply_markup=back_kb,
                )
                return

            lock = get_game_lock(query.message.chat.id)
            async with lock:
                if has_active_game(query.message.chat.id):
                    existing_game = active_games.get(query.message.chat.id)
                    await query.answer(
                        get_existing_game_message(existing_game),
                        show_alert=True,
                    )
                    return

            await start_game(update, context)
            return
        else:
            user_id = query.from_user.id
            bot_username = context.bot.username
            already_claimed = has_claimed_group_bonus(user_id)

            if not already_claimed:
                text = (
                    "🍋 Play Quiz in Groups!\n\n"
                    "Add English Lemon to your group and give it admin rights.\n\n"
                    "🎯 Bonus: Earn +1000 🍋 after your first completed game!\n\n"
                    "✅ Rules:\n"
                    "• One-time reward only\n"
                    "• Bot must have admin rights\n"
                    "• You must complete at least 1 game\n\n"
                    "👇 Start here:"
                )
            else:
                text = (
                    "🍋 Play Quiz in Groups!\n\n"
                    "Add English Lemon to your group and start playing with friends.\n\n"
                    "👇 Start here:"
                )

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "➕ Add to Group",
                        url=f"https://t.me/{bot_username}?startgroup=true"
                    )
                ],
                [
                    InlineKeyboardButton("⬅️ Back", callback_data="menu_back")
                ],
            ])

            await query.edit_message_text(
                text,
                reply_markup=keyboard,
            )
            return

    if data == "menu_leaderboard":
        await leaderboard(update, context)
        return

    if data == "menu_profile":
        await profile(update, context)
        return

    if data == "menu_help":
        await query.edit_message_text(
            "English Lemon Commands:\n\n"
            "/start - open the main menu\n"
            "/startgame - start a new game in a group\n"
            "/stopgame - stop the current game\n"
            "/dailyquiz - play one daily quiz\n"
            "/leaderboard - leaderboard\n"
            "/daily - today's leaderboard\n"
            "/weekly - this week's leaderboard\n"
            "/monthly - this month's leaderboard\n"
            "/profile - your profile",
            reply_markup=back_kb,
        )
        return

    if data in ("menu_back", "menu_main"):
        chat_id = query.message.chat.id
        chat_type = query.message.chat.type

        if chat_type in ("group", "supergroup"):
            lock = get_game_lock(chat_id)
            async with lock:
                game = active_games.get(chat_id)

                if game:
                    status = game.get("status")

                    if status == "running":
                        await query.answer(
                            "You cannot close the menu while a game is running.",
                            show_alert=True,
                        )
                        return

                    if status in ("setup", "joining"):
                        allowed = is_admin(query.from_user.id) or await is_group_admin(
                            context,
                            chat_id,
                            query.from_user.id,
                        )

                        if not allowed:
                            await query.answer(
                                "Only group admins can cancel setup or joining.",
                                show_alert=True,
                            )
                            return

            await clear_game(context, chat_id)
        else:
            await clear_game(context, chat_id)

        await query.edit_message_text(
            "Welcome to English Lemon !\n\n"
            "Practice vocabulary, play quiz games, and climb the leaderboard.",
            reply_markup=get_main_menu_keyboard(),
        )
        return


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(update.effective_user.id))


async def daily_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_dynamic_settings()
    question_seconds = settings["QUESTION_SECONDS"]

    logger.warning("DAILY QUIZ COMMAND RECEIVED")

    user = update.effective_user
    chat = update.effective_chat
    today = str(date.today())

    if chat:
        ensure_chat(chat)

    if has_played_daily_quiz(user.id, today):
        await update.message.reply_text("You already played today’s daily quiz.")
        return

    ensure_player(user)

    try:
        question = get_random_question()
        logger.warning("Daily question fetched: %s", dict(question) if question else None)
    except Exception:
        logger.exception("Failed to fetch daily question")
        await update.message.reply_text("❌ Failed to load daily question.")
        return

    if not question:
        await update.message.reply_text("No questions available.")
        return

    try:
        q_id = question["id"]
        q_text = question["question_text"]
        difficulty = row_value(question, "difficulty", "easy")
        points = get_question_points(difficulty)

        options, correct_index = shuffle_question(question)

        if correct_index not in (0, 1, 2, 3):
            await update.message.reply_text("This daily question has an invalid correct answer.")
            return

        msg = await context.bot.send_poll(
            chat_id=chat.id,
            question=format_question_text(q_text, points),
            options=options,
            type="quiz",
            correct_option_id=correct_index,
            is_anonymous=False,
            open_period=question_seconds,
        )
    except Exception:
        logger.exception("Failed to send daily quiz poll for user %s", user.id)
        await update.message.reply_text("Failed to send the daily quiz.\nPlease try again.")
        return

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


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("START GAME COMMAND RECEIVED")

    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message
    query = update.callback_query

    if chat:
        ensure_chat(chat)

    if not user:
        if query:
            await query.edit_message_text("❌ Admin only.")
        else:
            await message.reply_text("❌ Admin only.")
        return

    allowed = is_admin(user.id)
    if chat.type in ("group", "supergroup"):
        allowed = allowed or await is_group_admin(context, chat.id, user.id)

    if not allowed:
        if query:
            await query.edit_message_text("❌ Only group admins can start a quiz game.")
        else:
            await message.reply_text("❌ Only group admins can start a quiz game.")
        return

    if chat.type == "private":
        if query:
            await query.edit_message_text("Use /startgame in a group.")
        else:
            await message.reply_text("Use /startgame in a group.")
        return

    lock = get_game_lock(chat.id)
    async with lock:
        if has_active_game(chat.id):
            existing_game = active_games.get(chat.id)
            text = get_existing_game_message(existing_game)

            if query:
                await query.answer(text, show_alert=True)
            else:
                await message.reply_text(text)
            return

        game = create_new_game_data(
            started_by=user.id,
            questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
            category=DEFAULT_CATEGORY,
            difficulty="mixed",
        )

        add_player_to_game(game, user)
        active_games[chat.id] = game

    text = format_setup_step_1_text()
    keyboard = get_question_count_keyboard()

    if query:
        await query.edit_message_text(text, reply_markup=keyboard)
    else:
        await message.reply_text(text, reply_markup=keyboard)


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.warning("STOP GAME COMMAND RECEIVED")

    chat = update.effective_chat
    user = update.effective_user

    if not user:
        await update.message.reply_text("Admin only.")
        return

    allowed = is_admin(user.id)
    if chat.type in ("group", "supergroup"):
        allowed = allowed or await is_group_admin(context, chat.id, user.id)

    if not allowed:
        await update.message.reply_text("Admin only.")
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


async def game_setup_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_dynamic_settings()
    join_seconds = settings["JOIN_SECONDS"]

    query = update.callback_query
    logger.warning("SETUP CALLBACK: %s", query.data)

    data = query.data

    if (
        not data.startswith("setup_")
        and data not in ("menu_back", "menu_main")
        and not data.startswith("setup_back_to_results:")
    ):
        return False

    await query.answer()

    user = query.from_user
    chat_id = query.message.chat.id

    if data.startswith("setup_back_to_results:"):
        try:
            _, _, game_id_str = data.split(":")
            game_id = int(game_id_str)
        except Exception:
            await query.answer("Error.", show_alert=True)
            return True

        # ✅ NOW INSIDE THE BLOCK
        all_pages = context.bot_data.get("final_results_pages", {})
        all_results = all_pages.get(game_id)

        if not all_results:
            await query.edit_message_text("Results not available.")
            return True

        await clear_game(context, chat_id)

        text, has_next = format_final_results_page(all_results, page=1)
        markup = final_results_keyboard(game_id, 1, has_next)

        await query.edit_message_text(
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
        return True

    # default back/menu behavior
    if data in ("menu_back", "menu_main"):
        await clear_game(context, chat_id)
        await query.edit_message_text(
            "Welcome to English Lemon !\n\n"
            "Practice vocabulary, play quiz games, and climb the leaderboard.",
            reply_markup=get_main_menu_keyboard(),
        )
        return True

    allowed = is_admin(user.id) or await is_group_admin(context, chat_id, user.id)
    if not allowed:
        await query.answer("Admin only.", show_alert=True)
        return True

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game or game.get("status") not in ("setup", "joining"):
            await query.edit_message_text("No active game setup found.")
            return True

        if game["status"] == "joining" and data.startswith("setup_"):
            await query.answer("Game already started.", show_alert=True)
            return True

        if data.startswith("setup_questions_"):
            try:
                count = int(data.split("_")[-1])
            except ValueError:
                await query.answer("Invalid question count.", show_alert=True)
                return True

            if count not in ALLOWED_QUESTION_COUNTS:
                await query.answer("Invalid question count.", show_alert=True)
                return True

            game["questions_per_game"] = count

            await query.edit_message_text(
                format_setup_step_2_text(count),
                reply_markup=get_category_keyboard(),
            )
            return True

        if data == "setup_back_to_questions":
            back_callback = "menu_main"
            if game.get("return_to_results"):
                back_callback = f"setup_back_to_results:{game['return_to_results']}"

            await query.edit_message_text(
                format_setup_step_1_text(),
                reply_markup=get_question_count_keyboard(back_callback=back_callback),
            )
            return True

        if data.startswith("setup_category_"):
            category = data.replace("setup_category_", "", 1)

            if category not in ALLOWED_CATEGORIES:
                await query.answer("Invalid category.", show_alert=True)
                return True

            game["category"] = category
            game["difficulty"] = "mixed"

            await query.edit_message_text(
                format_setup_summary(
                    question_count=game["questions_per_game"],
                    category=game["category"],
                ),
                reply_markup=get_setup_confirmation_keyboard(),
            )
            return True

        if data == "setup_back_to_categories":
            await query.edit_message_text(
                format_setup_step_2_text(game["questions_per_game"]),
                reply_markup=get_category_keyboard(),
            )
            return True

        if data == "setup_start_game":
            if game.get("status") != "setup":
                await query.answer("Game already started.", show_alert=True)
                return True

            try:
                game["min_players"] = settings["MIN_PLAYERS"]
                mark_game_joining(game, join_seconds)

                await query.edit_message_text(
                    text=build_join_text(game, join_seconds),
                    reply_markup=get_join_keyboard(chat_id),
                    parse_mode="HTML",
                )

                game["join_message_id"] = query.message.message_id

                safe_task(begin_game_after_join(chat_id, context))
                return True

            except Exception:
                logger.exception("Failed in setup_start_game for chat %s", chat_id)
                await query.answer("Failed to start registration.", show_alert=True)
                return True

        return False


async def begin_game_after_join(chat_id, context):
    settings = load_dynamic_settings()
    min_players = settings["MIN_PLAYERS"]
    join_seconds = settings["JOIN_SECONDS"]

    logger.warning("BEGIN GAME AFTER JOIN: %s", chat_id)

    try:
        loop = asyncio.get_event_loop()

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if not game or game["status"] != "joining":
                return

            game["join_end_time"] = loop.time() + join_seconds
            game["display_remaining"] = join_seconds
            game["display_blink"] = False

        last_display_value = None
        last_blink = None

        while True:
            lock = get_game_lock(chat_id)
            async with lock:
                game = active_games.get(chat_id)
                if not game or game["status"] != "joining":
                    return

                end_time = game.get("join_end_time")
                if end_time is None:
                    return

                actual_remaining = max(0, int(end_time - loop.time()))

                if actual_remaining > 10:
                    display_value = ((actual_remaining + 9) // 10) * 10
                    display_value = min(display_value, join_seconds)
                    blink = False
                else:
                    display_value = actual_remaining
                    blink = (actual_remaining % 2 == 0)

                game["display_remaining"] = display_value
                game["display_blink"] = blink

            if display_value != last_display_value or blink != last_blink:
                await refresh_join_message(context, chat_id)
                last_display_value = display_value
                last_blink = blink

            if actual_remaining <= 0:
                break

            await asyncio.sleep(1)

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if not game or game["status"] != "joining":
                return

            join_message_id = game.get("join_message_id")

            if len(game["players"]) < min_players:
                active_games.pop(chat_id, None)
                cleanup_game_lock(chat_id)
                not_enough_players = True
            else:
                game["status"] = "running"
                not_enough_players = False

        await safe_delete_message(context.bot, chat_id, join_message_id)

        if not_enough_players:
            await context.bot.send_message(
                chat_id,
                f"❌ Not enough players.\nGame cancelled.\n\nMinimum players needed: {min_players}",
            )
            return

        lock = get_game_lock(chat_id)
        async with lock:
            game = active_games.get(chat_id)
            if not game or game["status"] != "running":
                return

            try:
                game["db_game_id"] = create_game(
                    chat_id=chat_id,
                    total_players=len(game["players"]),
                    total_rounds=game["questions_per_game"],
                    status="running",
                )
            except Exception:
                logger.exception("Failed to create game record for chat %s", chat_id)

        await context.bot.send_message(
            chat_id,
            "Game started! Get ready for the first question."
        )
        await send_question(chat_id, context)

    except Exception:
        logger.exception("Error in begin_game_after_join for chat %s", chat_id)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.warning("BUTTON CALLBACK: %s", query.data)

    data = query.data

    # 🔥 IMPORTANT FIX
    if (
        data.startswith("setup_")
        or data in ("menu_back", "menu_main")
        or data.startswith("setup_back_to_results:")
    ):
        handled = await game_setup_callback_handler(update, context)
        if handled is True:
            return

    parts = data.split("|")

    if parts[0] != "join":
        await query.answer()
        return

    try:
        chat_id = int(parts[1])
    except (IndexError, ValueError):
        await query.answer("Invalid join request.")
        return

    if query.message and query.message.chat:
        ensure_chat(query.message.chat)

    lock = get_game_lock(chat_id)

    async with lock:
        game = active_games.get(chat_id)

        if not game:
            await query.answer("No active game")
            return

        if game["status"] != "joining":
            await query.answer("Joining closed")
            return

        user = query.from_user
        added = add_player_to_game(game, user)

        if not added:
            await query.answer("Already joined")
            return

    ensure_player(user)

    if chat_id < 0:
        ensure_group_player(chat_id, user)

    await refresh_join_message(context, chat_id)
    await query.answer("Joined!")


async def send_question(chat_id, context):
    settings = load_dynamic_settings()
    question_seconds = settings["QUESTION_SECONDS"]

    logger.warning("SEND QUESTION: %s", chat_id)

    should_end = False

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            return

        current_round, questions_per_game, should_end = start_next_round(game)

    if should_end:
        await end_game(chat_id, context)
        return

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            return

        try:
            question = get_unused_question(game)
            logger.warning("Fetched game question: %s", dict(question) if question else None)
        except Exception:
            logger.exception("Failed to fetch question for chat %s", chat_id)
            await context.bot.send_message(chat_id, "❌ Failed to load question from database.")
            await end_game(chat_id, context)
            return

        no_question = not question

    if no_question:
        await context.bot.send_message(
            chat_id,
            "No more unused questions available for this category/difficulty.\nEnding game.",
        )
        await end_game(chat_id, context)
        return

    try:
        q_id = question["id"]
        q_text = question["question_text"]
        difficulty = row_value(question, "difficulty", "easy")
        points = get_question_points(difficulty)

        options, correct_index = shuffle_question(question)

        if correct_index not in (0, 1, 2, 3):
            await context.bot.send_message(
                chat_id,
                f"Question ID {q_id} has an invalid correct option.",
            )
            await end_game(chat_id, context)
            return

        poll_question = format_question_text(q_text, points)

        msg = await context.bot.send_poll(
            chat_id=chat_id,
            question=poll_question,
            options=options,
            type="quiz",
            correct_option_id=correct_index,
            is_anonymous=False,
            open_period=question_seconds,
        )
    except Exception:
        logger.exception("Failed to send poll in chat %s round %s", chat_id, current_round)
        await context.bot.send_message(chat_id, "Failed to send the next question.\nEnding game.")
        await end_game(chat_id, context)
        return

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            poll_map.pop(msg.poll.id, None)
            return

        prepare_round_state(game, msg.poll.id, q_id, correct_index)

    poll_map[msg.poll.id] = {
        "chat_id": chat_id,
        "round": current_round,
        "question_id": q_id,
        "difficulty": difficulty,
        "points": points,
    }

    logger.info("Sent poll %s in chat %s for round %s", msg.poll.id, chat_id, current_round)
    safe_task(wait_and_continue(chat_id, context, msg.poll.id, current_round))


async def wait_and_continue(chat_id, context, poll_id, round_number):
    settings = load_dynamic_settings()
    question_seconds = settings["QUESTION_SECONDS"]

    await asyncio.sleep(question_seconds + 1)

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game or game["status"] != "running":
            poll_map.pop(poll_id, None)
            return

        if game.get("current_poll_id") != poll_id:
            poll_map.pop(poll_id, None)
            return

    poll_map.pop(poll_id, None)
    await send_question(chat_id, context)


async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = load_dynamic_settings()
    points_map = settings["POINTS"]
    speed_bonus_seconds = settings["SPEED_BONUS_SECONDS"]
    speed_bonus_points = settings["SPEED_BONUS_POINTS"]

    answer = update.poll_answer
    poll_id = answer.poll_id
    info = poll_map.get(poll_id)

    if not info:
        return

    if info.get("round") == "daily":
        user = answer.user
        ensure_player(user)

        if user.id != info.get("daily_user_id"):
            return

        points = info.get("points", CORRECT_POINTS)

        if answer.option_ids and answer.option_ids[0] == info["correct_index"]:
            add_points(user.id, points)
            record_correct_answer(user.id)

            if info["chat_id"] < 0:
                ensure_group_player(info["chat_id"], user)
                add_group_points(info["chat_id"], user, points)
                record_group_correct_answer(info["chat_id"], user)

            display_name = f"@{user.username}" if user.username else user.full_name
            msg = await context.bot.send_message(
                info["chat_id"],
                f"✅ {display_name} +{points} 🍋",
            )
            safe_task(delete_later(context, info["chat_id"], msg.message_id, 4))
        else:
            record_wrong_answer(user.id)

            if info["chat_id"] < 0:
                ensure_group_player(info["chat_id"], user)
                record_group_wrong_answer(info["chat_id"], user)

            msg = await context.bot.send_message(
                info["chat_id"],
                f"🎯 Daily Quiz\n❌ {user.full_name} got it wrong.",
            )
            safe_task(delete_later(context, info["chat_id"], msg.message_id, 4))

        poll_map.pop(poll_id, None)
        return

    chat_id = info["chat_id"]

    lock = get_game_lock(chat_id)
    async with lock:
        game = active_games.get(chat_id)
        if not game:
            return

        user = answer.user
        ensure_player(user)

        base_points = info.get("points", points_map["easy"])

        result = apply_poll_answer(
            game=game,
            user_id=user.id,
            option_ids=answer.option_ids,
            correct_points=base_points,
            speed_bonus_seconds=speed_bonus_seconds,
            speed_bonus_points=speed_bonus_points,
        )

        if result is None:
            return

        is_correct = result["is_correct"]
        points_to_add = result["points_to_add"]
        got_speed_bonus = result["got_speed_bonus"]
        elapsed = result["elapsed"]

    if is_correct:
        add_points(user.id, points_to_add)
        record_correct_answer(user.id, answer_time=elapsed)

        if chat_id < 0:
            ensure_group_player(chat_id, user)
            add_group_points(chat_id, user, points_to_add)
            record_group_correct_answer(chat_id, user)

        display_name = f"@{user.username}" if user.username else user.full_name

        reward_text = f"✅ {display_name} +{base_points} 🍋"
        if got_speed_bonus:
            reward_text += f"\n⚡ Speed bonus +{speed_bonus_points}"

        msg = await context.bot.send_message(chat_id, reward_text)
        safe_task(delete_later(context, chat_id, msg.message_id, 4))
    else:
        record_wrong_answer(user.id)

        if chat_id < 0:
            ensure_group_player(chat_id, user)
            record_group_wrong_answer(chat_id, user)


async def delete_later(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 4):
    await asyncio.sleep(delay)
    await safe_delete_message(context.bot, chat_id, message_id)


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
        scores = game.get("scores", {})
        correct_counts = game.get("correct_counts", {})
        wrong_counts = game.get("wrong_counts", {})

        if poll_id:
            poll_map.pop(poll_id, None)

        normalized_results = []

        for user_id, player_data in players.items():
            raw_name = (
                player_data.get("full_name")
                or player_data.get("name")
                or player_data.get("username")
                or "Unknown"
            )

            safe_name = str(raw_name).replace("<", "&lt;").replace(">", "&gt;")
            name = f'<a href="tg://user?id={user_id}">{safe_name}</a>'

            normalized_results.append({
                "user_id": user_id,
                "full_name": name,
                "points": scores.get(user_id, 0),
                "correct_answers": correct_counts.get(user_id, 0),
                "wrong_answers": wrong_counts.get(user_id, 0),
            })

        normalized_results.sort(
            key=lambda x: (
                x["points"],
                x["correct_answers"],
                -x["wrong_answers"],
            ),
            reverse=True,
        )

        winner_user_id = None
        if normalized_results:
            winner_user_id = normalized_results[0].get("user_id")

        game_id = chat_id
        context.bot_data.setdefault("final_results_pages", {})
        context.bot_data["final_results_pages"][chat_id] = normalized_results

        # 🔥 ALSO STORE LAST RESULT
        context.bot_data["last_results"] = normalized_results

        active_games.pop(chat_id, None)
        cleanup_game_lock(chat_id)

    try:
        if db_game_id:
            finish_game(
                game_id=db_game_id,
                winner_user_id=winner_user_id,
                total_players=len(players),
                total_rounds=total_rounds,
                status="finished",
            )
    except Exception:
        logger.exception("Failed to finish game for chat %s", chat_id)

    try:
        for user_id in players.keys():
            increment_games_played(user_id)
            if chat_id < 0:
                increment_group_games_played(chat_id, user_id)

            score = scores.get(user_id, 0)
            correct = correct_counts.get(user_id, 0)
            wrong = wrong_counts.get(user_id, 0)

            record_game_result(
                user_id=user_id,
                chat_id=chat_id,
                score=score,
                correct_answers=correct,
                wrong_answers=wrong,
                is_winner=(user_id == winner_user_id),
            )

        if winner_user_id:
            increment_games_won(winner_user_id)
            if chat_id < 0:
                increment_group_games_won(chat_id, winner_user_id)
    except Exception:
        logger.exception("Failed to save final game stats for chat %s", chat_id)

    if normalized_results:
        text, has_next = format_final_results_page(normalized_results, page=1)
        markup = final_results_keyboard(game_id, 1, has_next)

        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🏁 Game finished.",
        )

    await try_give_group_bonus(chat_id, {"players": players}, context)