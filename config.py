import os
import logging

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "quiz.db")

ADMIN_ID = 8368997991

MIN_PLAYERS = 3
JOIN_SECONDS = 60
QUESTION_SECONDS = 15

SPEED_BONUS_SECONDS = 5
CORRECT_POINTS = 25
SPEED_BONUS_POINTS = 10

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing! Add it to Railway variables or environment variables.")