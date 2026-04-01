from database import (
    get_total_users_count,
    get_total_players,
    get_total_questions_count,
    get_total_games,
    get_total_groups,
)


def get_bot_stats_service():
    return {
        "total_users": get_total_users_count(),
        "total_players": get_total_players(),
        "total_questions": get_total_questions_count(),
        "total_games": get_total_games(),
        "total_groups": get_total_groups(),
    }