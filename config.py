import os
import logging

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "/data/quiz.db")

ADMIN_ID = 8368997991

MIN_PLAYERS = 3
JOIN_SECONDS = 60
QUESTION_SECONDS = 15

DEFAULT_QUESTIONS_PER_GAME = 5
ALLOWED_QUESTION_COUNTS = [5, 10, 15, 20]

DEFAULT_CATEGORY = "mixed"
ALLOWED_CATEGORIES = ["mixed", "vocabulary", "grammar", "idioms", "synonyms"]

SPEED_BONUS_SECONDS = 5
CORRECT_POINTS = 25
SPEED_BONUS_POINTS = 10

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing! Add it to Railway variables or environment variables.")