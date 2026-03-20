from telegram import InlineKeyboardButton, InlineKeyboardMarkup


LEADERBOARD_PAGE_SIZE = 15


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Quiz", callback_data="menu_play")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("👤 My Profile", callback_data="menu_profile")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ])


def back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=callback_data)],
    ])


def leaderboard_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌍 Global", callback_data="leaderboard_global"),
            InlineKeyboardButton("👥 Group", callback_data="leaderboard_group"),
        ],
        [
            InlineKeyboardButton("📅 Daily", callback_data="leaderboard_daily"),
            InlineKeyboardButton("🗓 Weekly", callback_data="leaderboard_weekly"),
        ],
        [
            InlineKeyboardButton("📆 Monthly", callback_data="leaderboard_monthly"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="menu_main"),
        ],
    ])


def game_setup_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5", callback_data="setup_questions_5"),
            InlineKeyboardButton("10", callback_data="setup_questions_10"),
        ],
        [
            InlineKeyboardButton("15", callback_data="setup_questions_15"),
            InlineKeyboardButton("20", callback_data="setup_questions_20"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="menu_main"),
        ],
    ])


def game_setup_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Mixed", callback_data="setup_category_mixed"),
            InlineKeyboardButton("Vocabulary", callback_data="setup_category_vocabulary"),
        ],
        [
            InlineKeyboardButton("Grammar", callback_data="setup_category_grammar"),
            InlineKeyboardButton("Idioms & Phrases", callback_data="setup_category_idioms_phrases"),
        ],
        [
            InlineKeyboardButton("Synonyms", callback_data="setup_category_synonyms"),
            InlineKeyboardButton("Collocations", callback_data="setup_category_collocations"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="setup_back_to_questions"),
        ],
    ])


def game_setup_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start Game", callback_data="setup_start_game")],
        [InlineKeyboardButton("⬅️ Back", callback_data="setup_back_to_categories")],
    ])