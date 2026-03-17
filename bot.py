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
)

from handlers.profile import (
    profile,
    leaderboard,
    global_leaderboard,
)

from handlers.admin import (
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
    QUESTION,
    A,
    B,
    C,
    D,
    CORRECT,
    DELETE_ID,
)


def main():
    create_tables()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("stopgame", stop_game))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("global", global_leaderboard))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("questions", questions_list))
    app.add_handler(CommandHandler("myid", myid))

    add_question_conv = ConversationHandler(
        entry_points=[CommandHandler("addquestion", add_question_start)],
        states={
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_step)],
            A: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_step)],
            B: [MessageHandler(filters.TEXT & ~filters.COMMAND, b_step)],
            C: [MessageHandler(filters.TEXT & ~filters.COMMAND, c_step)],
            D: [MessageHandler(filters.TEXT & ~filters.COMMAND, d_step)],
            CORRECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, correct_step)],
        },
        fallbacks=[],
    )

    delete_question_conv = ConversationHandler(
        entry_points=[CommandHandler("deletequestion", delete_question_start)],
        states={
            DELETE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_id_step)],
        },
        fallbacks=[],
    )

    app.add_handler(add_question_conv)
    app.add_handler(delete_question_conv)

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PollAnswerHandler(receive_poll_answer))

    print("Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()