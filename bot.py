# bot.py
import logging

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ConversationHandler,
    MessageHandler,
    ChatMemberHandler,
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
    myid,
    final_results_callback_handler,
)

from handlers.profile import (
    profile,
    leaderboard,
    daily,
    weekly,
    monthly,
    global_leaderboard,
    profile_callback_handler,
)

from handlers.group_bonus import bot_added_to_group_handler

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
    edit_text_only_step,
    edit_option_only_step,
    edit_correct_only_step,
    edit_category_only_step,
    edit_difficulty_only_step,
    EDIT_TEXT_ONLY,
    EDIT_OPTION_ONLY,
    EDIT_CORRECT_ONLY,
    EDIT_CATEGORY_ONLY,
    EDIT_DIFFICULTY_ONLY,
    settings_update_step,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    logger.warning("BOT STARTED")
    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()

    # ================= ADMIN =================
    admin_conv = ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_panel),
            CallbackQueryHandler(
                admin_button_handler,
                pattern=r"^(admin_|edit_|settings_)",
            ),
            CallbackQueryHandler(
                import_questions_entry,
                pattern=r"^admin_import_questions$",
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
            DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_confirm_step)],
            EDIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_id_step)],
            EDIT_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_question_step)],
            EDIT_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_a_step)],
            EDIT_B: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_b_step)],
            EDIT_C: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_c_step)],
            EDIT_D: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_d_step)],
            EDIT_CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_correct_step)],
            EDIT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_category_step)],
            EDIT_DIFFICULTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_difficulty_step)],

            EDIT_TEXT_ONLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_text_only_step)],
            EDIT_OPTION_ONLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_option_only_step)],
            EDIT_CORRECT_ONLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_correct_only_step)],
            EDIT_CATEGORY_ONLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_category_only_step)],
            EDIT_DIFFICULTY_ONLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_difficulty_only_step)],

            BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_message_step)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(broadcast_confirm_step)],
            IMPORT_FILE: [MessageHandler(filters.Document.ALL, import_questions_file_step)],
            SEARCH_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_keyword_step)],

            ADMIN_MENU: [
                CallbackQueryHandler(
                    admin_button_handler,
                    pattern=r"^(admin_|edit_|settings_)",
                )
            ],

            1000: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_update_step)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=r"^admin_close$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(admin_conv)

    # ================= COMMANDS =================
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", start_game))
    app.add_handler(CommandHandler("stopgame", stop_game))

    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("global", global_leaderboard))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("weekly", weekly))
    app.add_handler(CommandHandler("monthly", monthly))
    app.add_handler(CommandHandler("profile", profile))

    app.add_handler(CommandHandler("botstats", bot_stats_command))
    app.add_handler(CommandHandler("dailyquiz", daily_quiz))
    app.add_handler(CommandHandler("myid", myid))

    # ================= CALLBACKS =================
    # Final results pagination first
    app.add_handler(
        CallbackQueryHandler(
            final_results_callback_handler,
            pattern=r"^final_results:",
        )
    )

    # Setup / join / back callbacks that must stay inside game flow
    app.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^(setup_|setup_back_to_results:|menu_back$|menu_main$|join\|)",
        )
    )

    # Main menu + play again
    app.add_handler(
        CallbackQueryHandler(
            menu_handler,
            pattern=r"^(menu_|results_play_again:)",
        )
    )

    # Leaderboard / profile callbacks
    app.add_handler(
        CallbackQueryHandler(
            profile_callback_handler,
            pattern=r"^(profile|leaderboard_.*)$",
        )
    )

    app.add_handler(PollAnswerHandler(receive_poll_answer))

    app.add_handler(
        ChatMemberHandler(
            bot_added_to_group_handler,
            ChatMemberHandler.MY_CHAT_MEMBER,
        )
    )

    logger.warning("RUNNING POLLING")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()