# config.py

import os
from dotenv import load_dotenv

# Load local .env for VS Code/debugging.
# On Railway, Railway environment variables will still work.
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_PATH = os.getenv("DB_PATH", "quiz_bot.db")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

MIN_PLAYERS = 1
JOIN_SECONDS = 60
QUESTION_SECONDS = 15

CORRECT_POINTS = 10
SPEED_BONUS_SECONDS = 5
SPEED_BONUS_POINTS = 5

DEFAULT_QUESTIONS_PER_GAME = 10
ALLOWED_QUESTION_COUNTS = [5, 10, 15, 20]

DEFAULT_CATEGORY = "mixed"
ALLOWED_CATEGORIES = [
    "mixed",
    "vocabulary",
    "grammar",
    "idioms_phrases",
    "synonyms",
    "collocations",
]

DEFAULT_DIFFICULTY = "mixed"
ALLOWED_DIFFICULTIES = ["easy", "medium", "hard", "mixed"]

POINTS = {
    "easy": 15,
    "medium": 25,
    "hard": 35,
}