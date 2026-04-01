import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import DEFAULT_QUESTIONS_PER_GAME, DEFAULT_CATEGORY
from database import ensure_player, ensure_user, ensure_chat, has_claimed_group_bonus
from handlers.profile import profile, leaderboard
from handlers.challenge import challenge_menu
from services.game_service import (
    active_games,
    get_game_lock,
    clear_game,
    create_new_game_data,
    get_existing_game_message,
    add_player_to_game,
)
from utils.helpers import is_admin, is_group_admin
from utils.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)


def get_main_menu_keyboard():
    return main_menu_keyboard()


async def block_group_menu_during_game(query, context, action_name: str) -> bool:
    chat = query.message.chat
    if chat.type not in ("group", "supergroup"):
        return False

    lock = get_game_lock(chat.id)
    async with lock:
        game = active_games.get(chat.id)
        if game and game.get("status") in ("setup", "joining", "running"):
            await query.answer(
                f"You cannot open {action_name} during setup or an active game.",
                show_alert=True,
            )
            return True

    return False


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

    if data.startswith("setup_") or data.startswith("setup_back_to_results:"):
        return

    back_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]]
    )

    if data == "menu_challenge":
        if await block_group_menu_during_game(query, context, "challenge"):
            return
        await challenge_menu(update, context)
        return

    if data.startswith("results_play_again:"):
        try:
            _, game_id_str = data.split(":")
            source_game_id = int(game_id_str)
        except Exception:
            await query.answer("Error.", show_alert=True)
            return

        chat_id = query.message.chat.id

        lock = get_game_lock(chat_id)
        async with lock:
            existing_game = active_games.get(chat_id)
            if existing_game and existing_game.get("status") in ("setup", "joining", "running"):
                await query.answer(
                    get_existing_game_message(existing_game),
                    show_alert=True,
                )
                return

            game = create_new_game_data(
                started_by=query.from_user.id,
                questions_per_game=DEFAULT_QUESTIONS_PER_GAME,
                category=DEFAULT_CATEGORY,
                difficulty="mixed",
            )
            game["return_to_results"] = source_game_id
            game["mode"] = "solo"

            add_player_to_game(game, query.from_user)
            active_games[chat_id] = game

        from handlers.game_setup import format_setup_step_1_text, get_question_count_keyboard

        await query.edit_message_text(
            format_setup_step_1_text(),
            reply_markup=get_question_count_keyboard(
                back_callback=f"setup_back_to_results:{source_game_id}"
            ),
        )
        return

    from handlers.game_setup import start_game, has_active_game

    if data == "menu_play":
        context.user_data["game_mode"] = "solo"

        if query.message.chat.type in ("group", "supergroup"):
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
        if await block_group_menu_during_game(query, context, "leaderboard"):
            return
        await leaderboard(update, context)
        return

    if data == "menu_profile":
        if await block_group_menu_during_game(query, context, "profile"):
            return
        await profile(update, context)
        return

    if data == "menu_help":
        if await block_group_menu_during_game(query, context, "help"):
            return
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