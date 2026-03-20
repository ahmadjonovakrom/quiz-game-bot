import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

MIN_PLAYERS = 1
JOIN_SECONDS = 20
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