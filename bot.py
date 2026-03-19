import logging

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ConversationHandler,
    MessageHandler,
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
    daily_leaderboard,
    weekly_leaderboard,
    monthly_leaderboard,
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
    SEARCH_KEYWORD,
    BROADCAST_MESSAGE,
    BROADCAST_CONFIRM,
    IMPORT_FILE,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main():
    create_tables()

    application = Application.builder().token(BOT_TOKEN).build()

    # -------- COMMANDS --------
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", start_game))
    application.add_handler(CommandHandler("stopgame", stop_game))
    application.add_handler(CommandHandler("dailyquiz", daily_quiz))
    application.add_handler(CommandHandler("profile", profile))

    # Leaderboards
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("global", global_leaderboard))
    application.add_handler(CommandHandler("daily", daily_leaderboard))
    application.add_handler(CommandHandler("weekly", weekly_leaderboard))
    application.add_handler(CommandHandler("monthly", monthly_leaderboard))

    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("botstats", bot_stats_command))
    application.add_handler(CommandHandler("importquestions", import_questions_entry))
    application.add_handler(CommandHandler("myid", myid))

    # -------- ADMIN CONVERSATION --------
    admin_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_panel),
            CallbackQueryHandler(
                admin_button_handler,
                pattern=(
                    r"^admin_"
                    r"|^confirm_delete_"
                    r"|^broadcast_"
                ),
            ),
        ],
        states={
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_step)],
            A: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_step)],
            B: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_step)],
            C: [MessageHandler(filters.TEXT & ~filters.COMMAND, c_step)],
            D: [MessageHandler(filters.TEXT & ~filters.COMMAND, d_step)],
            CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, correct_step)],

            DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_id_step)],
            DELETE_CONFIRM: [
                CallbackQueryHandler(delete_confirm_step, pattern=r"^confirm_delete_(yes|no)$")
            ],

            EDIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_id_step)],
            EDIT_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_question_step)],
            EDIT_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_a_step)],
            EDIT_B: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_b_step)],
            EDIT_C: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_c_step)],
            EDIT_D: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_d_step)],
            EDIT_CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_correct_step)],
            EDIT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_category_step)],
            EDIT_DIFFICULTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_difficulty_step)],

            SEARCH_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_keyword_step)],

            BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message_step)
            ],
            BROADCAST_CONFIRM: [
                CallbackQueryHandler(broadcast_confirm_step, pattern=r"^broadcast_(yes|no)$")
            ],

            IMPORT_FILE: [
                MessageHandler(filters.Document.ALL & ~filters.COMMAND, import_questions_file_step)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=r"^admin_close$"),
        ],
        allow_reentry=True,
    )
    application.add_handler(admin_conversation)

    # -------- CALLBACKS --------
    application.add_handler(
        CallbackQueryHandler(
            profile_callback_handler,
            pattern=r"^lb_(global|group|daily|weekly|monthly)_\d+$|^lb_myrank$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            game_setup_callback_handler,
            pattern=r"^(quiz_count_|quiz_category_|quiz_difficulty_|quiz_start_confirm)",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            menu_handler,
            pattern=r"^(menu_|profile$|play_quiz$)",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^(join_quiz|stop_quiz)$",
        )
    )

    # -------- POLL ANSWERS --------
    application.add_handler(PollAnswerHandler(receive_poll_answer))

    logger.info("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()