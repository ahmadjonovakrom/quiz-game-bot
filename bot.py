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
    profile_callback_handler,
)

from handlers.admin import (
    admin_panel,
    admin_button_handler,
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
    broadcast_message_step,
    broadcast_confirm_step,
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
    BROADCAST_MESSAGE,
    BROADCAST_CONFIRM,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()

    admin_conv = ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_panel),
            CallbackQueryHandler(
                admin_button_handler,
                pattern=r"^(admin_questions|admin_add_question|admin_delete_question|admin_edit_question|admin_list_questions|admin_botstats|admin_broadcast|admin_back|admin_close)$",
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
            DELETE_CONFIRM: [CallbackQueryHandler(delete_confirm_step, pattern=r"^confirm_delete_(yes|no)$")],

            EDIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_id_step)],
            EDIT_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_question_step)],
            EDIT_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_a_step)],
            EDIT_B: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_b_step)],
            EDIT_C: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_c_step)],
            EDIT_D: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_d_step)],
            EDIT_CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_correct_step)],

            BROADCAST_MESSAGE: [
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO | filters.VOICE)
                    & ~filters.COMMAND,
                    broadcast_message_step,
                )
            ],
            BROADCAST_CONFIRM: [
                CallbackQueryHandler(broadcast_confirm_step, pattern=r"^broadcast_(yes|no)$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("play", start_game))
    app.add_handler(CommandHandler("stopgame", stop_game))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("global", global_leaderboard))
    app.add_handler(CommandHandler("dailyquiz", daily_quiz))

    app.add_handler(admin_conv)

    app.add_handler(CallbackQueryHandler(menu_handler, pattern=r"^menu_"))
    app.add_handler(CallbackQueryHandler(profile_callback_handler, pattern=r"^lb_"))
    app.add_handler(CallbackQueryHandler(game_setup_callback_handler, pattern=r"^setup_"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern=r"^join\|"))

    app.add_handler(PollAnswerHandler(receive_poll_answer))

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()