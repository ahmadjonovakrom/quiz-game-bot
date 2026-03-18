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
    myid,
    start_game,
    stop_game,
    button_handler,
    receive_poll_answer,
    menu_handler,
    daily_quiz,
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
    questions_list,
    add_question_start,
    question_step,
    a_step,
    b_step,
    c_step,
    d_step,
    correct_step,
    delete_question_start,
    delete_id_step,
    delete_confirm_step,
    edit_question_start,
    edit_id_step,
    edit_question_step,
    edit_a_step,
    edit_b_step,
    edit_c_step,
    edit_d_step,
    edit_correct_step,
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
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main():
    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()

    # -------------------------
    # Basic commands
    # -------------------------
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))

    # -------------------------
    # Game commands
    # -------------------------
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("stopgame", stop_game))
    app.add_handler(CommandHandler("dailyquiz", daily_quiz))

    # -------------------------
    # Profile / leaderboard
    # -------------------------
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("global", global_leaderboard))
    app.add_handler(CommandHandler("profile", profile))

    # -------------------------
    # Admin simple commands
    # -------------------------
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("questions", questions_list))

    # -------------------------
    # Admin conversations
    # -------------------------
    add_question_conv = ConversationHandler(
        entry_points=[
            CommandHandler("addquestion", add_question_start),
            CallbackQueryHandler(admin_button_handler, pattern=r"^admin_add$"),
        ],
        states={
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_step)],
            A: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_step)],
            B: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_step)],
            C: [MessageHandler(filters.TEXT & ~filters.COMMAND, c_step)],
            D: [MessageHandler(filters.TEXT & ~filters.COMMAND, d_step)],
            CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, correct_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    delete_question_conv = ConversationHandler(
        entry_points=[
            CommandHandler("deletequestion", delete_question_start),
            CallbackQueryHandler(admin_button_handler, pattern=r"^admin_delete$"),
            CallbackQueryHandler(admin_button_handler, pattern=r"^qdelete\|\d+$"),
        ],
        states={
            DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_id_step)],
            DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_confirm_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    edit_question_conv = ConversationHandler(
        entry_points=[
            CommandHandler("editquestion", edit_question_start),
            CallbackQueryHandler(admin_button_handler, pattern=r"^admin_edit$"),
            CallbackQueryHandler(admin_button_handler, pattern=r"^qedit\|\d+$"),
        ],
        states={
            EDIT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_id_step)],
            EDIT_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_question_step)],
            EDIT_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_a_step)],
            EDIT_B: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_b_step)],
            EDIT_C: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_c_step)],
            EDIT_D: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_d_step)],
            EDIT_CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_correct_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    app.add_handler(add_question_conv)
    app.add_handler(delete_question_conv)
    app.add_handler(edit_question_conv)

    # -------------------------
    # Other callback handlers
    # -------------------------
    app.add_handler(CallbackQueryHandler(profile_callback_handler, pattern=r"^(menu_leaderboard|lb_)"))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern=r"^menu_"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern=r"^join\|"))

    # Optional safety fallback for admin callbacks that are not caught inside conversations
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern=r"^(admin_list|admin_add|admin_edit|admin_delete|qedit\|\d+|qdelete\|\d+)$"))

    # -------------------------
    # Poll answers
    # -------------------------
    app.add_handler(PollAnswerHandler(receive_poll_answer))

    logger.info("Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()