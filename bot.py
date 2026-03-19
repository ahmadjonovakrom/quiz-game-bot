# bot.py

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN
from database import create_tables

from handlers.game import (
    start,
    start_game,
    stop_game,
    button_handler,
    receive_poll_answer,
    menu_handler,
    daily_quiz,
    game_setup_callback_handler,
    myid,
)

from handlers.profile import (
    profile,
    leaderboard,
    global_leaderboard,
    profile_callback_handler,
)

from handlers.admin import (
    admin_panel,
    admin_button_handler,
    bot_stats_command,
    question_step,
    a_step,
    b_step,
    c_step,
    d_step,
    correct_step,
    delete_id_step,
    delete_confirm_step,
    edit_id_step,
    edit_question_step,
    edit_a_step,
    edit_b_step,
    edit_c_step,
    edit_d_step,
    edit_correct_step,
    edit_category_step,
    edit_difficulty_step,
    search_keyword_step,
    broadcast_message_step,
    broadcast_confirm_step,
    import_questions_entry,
    import_questions_file_step,
    cancel,
    ADMIN_MENU,
    QUESTION,
    A,
    B,
    C,
    D,
    CORRECT,
    DELETE_ID,
    DELETE_CONFIRM,
    EDIT_ID,
    EDIT_QUESTION,
    EDIT_A,
    EDIT_B,
    EDIT_C,
    EDIT_D,
    EDIT_CORRECT,
    EDIT_CATEGORY,
    EDIT_DIFFICULTY,
    BROADCAST_MESSAGE,
    BROADCAST_CONFIRM,
    IMPORT_FILE,
    SEARCH_KEYWORD,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled exception while processing update", exc_info=context.error)

    if isinstance(update, Update):
        try:
            if update.effective_message:
                await update.effective_message.reply_text(
                    "Something went wrong while processing that action."
                )
        except Exception:
            logger.exception("Failed to notify user about the error")


def build_admin_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_panel),
            CommandHandler("importquestions", import_questions_entry),
            CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
        ],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],

            QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, question_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            A: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, a_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            B: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, b_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            C: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, c_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            D: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, d_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            CORRECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, correct_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],

            DELETE_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_id_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            DELETE_CONFIRM: [
                CallbackQueryHandler(delete_confirm_step, pattern=r"^confirm_delete_(yes|no)$"),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],

            EDIT_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_id_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            EDIT_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_question_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            EDIT_A: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_a_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            EDIT_B: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_b_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            EDIT_C: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_c_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            EDIT_D: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_d_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            EDIT_CORRECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_correct_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            EDIT_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_category_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            EDIT_DIFFICULTY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_difficulty_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],

            SEARCH_KEYWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_keyword_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],

            BROADCAST_MESSAGE: [
                MessageHandler(
                    (
                        filters.TEXT
                        | filters.PHOTO
                        | filters.VIDEO
                        | filters.Document.ALL
                        | filters.AUDIO
                        | filters.VOICE
                    ) & ~filters.COMMAND,
                    broadcast_message_step,
                ),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
            BROADCAST_CONFIRM: [
                CallbackQueryHandler(broadcast_confirm_step, pattern=r"^broadcast_(yes|no)$"),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],

            IMPORT_FILE: [
                MessageHandler(filters.Document.ALL & ~filters.COMMAND, import_questions_file_step),
                CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True,
    )


def main():
    create_tables()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(False)
        .build()
    )

    admin_conv = build_admin_conversation()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("play", start_game))
    app.add_handler(CommandHandler("stopgame", stop_game))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("global", global_leaderboard))
    app.add_handler(CommandHandler("dailyquiz", daily_quiz))
    app.add_handler(CommandHandler("botstats", bot_stats_command))

    app.add_handler(admin_conv)

    app.add_handler(CallbackQueryHandler(menu_handler, pattern=r"^menu_"))
    app.add_handler(CallbackQueryHandler(profile_callback_handler, pattern=r"^lb_"))
    app.add_handler(CallbackQueryHandler(game_setup_callback_handler, pattern=r"^setup_"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern=r"^join\|"))

    app.add_handler(PollAnswerHandler(receive_poll_answer))
    app.add_error_handler(error_handler)

    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()