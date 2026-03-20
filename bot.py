import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    PollAnswerHandler,
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
    daily,
    weekly,
    monthly,
    profile_callback_handler,
)

from handlers.group_leaderboard import (
    group_leaderboard,
    group_daily,
    group_weekly,
    group_monthly,
    group_leaderboard_callback_handler,
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


async def error_handler(update, context):
    logger.exception("Unhandled exception while processing update", exc_info=context.error)


async def debug_callback(update, context):
    query = update.callback_query
    if query:
        logger.info("UNMATCHED CALLBACK DATA: %s", query.data)
        await query.answer()


def build_admin_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_panel),
            CallbackQueryHandler(admin_button_handler, pattern=r"^admin_"),
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
            BROADCAST_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_message_step)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(broadcast_confirm_step)],
            IMPORT_FILE: [MessageHandler(filters.Document.ALL, import_questions_file_step)],
            SEARCH_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_keyword_step)],
            ADMIN_MENU: [CallbackQueryHandler(admin_button_handler, pattern=r"^admin_")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=r"^admin_close$"),
        ],
        allow_reentry=True,
    )


def main():
    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(error_handler)

    # Admin conversation first
    app.add_handler(build_admin_conversation())

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", start_game))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("stopgame", stop_game))

    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("weekly", weekly))
    app.add_handler(CommandHandler("monthly", monthly))

    app.add_handler(CommandHandler("groupleaderboard", group_leaderboard))
    app.add_handler(CommandHandler("groupdaily", group_daily))
    app.add_handler(CommandHandler("groupweekly", group_weekly))
    app.add_handler(CommandHandler("groupmonthly", group_monthly))

    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("botstats", bot_stats_command))
    app.add_handler(CommandHandler("dailyquiz", daily_quiz))
    app.add_handler(CommandHandler("myid", myid))

    # Callback queries
    app.add_handler(
        CallbackQueryHandler(
            group_leaderboard_callback_handler,
            pattern=r"^group_lb_(all|daily|weekly|monthly)$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            game_setup_callback_handler,
            pattern=r"^(setup_questions_|setup_category_|setup_difficulty_)",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            profile_callback_handler,
            pattern=(
                r"^(leaderboard_global|leaderboard_group|"
                r"leaderboard_daily|leaderboard_weekly|leaderboard_monthly|"
                r"leaderboard_rank|leaderboard_menu|profile)$"
            ),
        )
    )

    app.add_handler(CallbackQueryHandler(menu_handler, pattern=r"^menu_"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern=r"^join\|"))

    # LAST: catch anything unmatched
    app.add_handler(CallbackQueryHandler(debug_callback))

    # Poll answers
    app.add_handler(PollAnswerHandler(receive_poll_answer))

    logger.info("Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()