from .connection import get_conn
from .schema import create_tables

# players
from .players import (
    ensure_player,
    get_player,
    add_points,
    add_manual_points,
    record_correct_answer,
    record_wrong_answer,
    increment_games_played,
    increment_games_won,
    get_top_players,
    get_global_leaderboard,
    get_global_leaderboard_page,
    get_player_rank,
    get_player_profile,
    get_player_global_rank_info,
    get_daily_leaderboard_page,
    get_weekly_leaderboard_page,
    get_monthly_leaderboard_page,
    get_player_daily_rank_info,
    get_player_weekly_rank_info,
    get_player_monthly_rank_info,
    get_all_user_ids,
    get_total_players,
    get_total_users_count,

    # 🔥 NEW FEATURES (YOU ASKED THIS)
    get_player_stats,
    get_player_full_profile,
    has_claimed_daily_reward,
    get_daily_reward_status,
    claim_daily_reward,
    reset_daily_streak_if_missed,
    get_player_streak_info,
)

# chats
from .chats import ensure_chat, deactivate_chat

# questions
from .questions import (
    add_question,
    question_exists,
    get_all_questions,
    get_question_by_id,
    update_question,
    delete_question,
    activate_question,
    deactivate_question,
    search_questions_by_keyword,
    export_questions_to_rows,
)

# groups
from .groups import (
    add_group_points,
    get_group_leaderboard,
    get_player_group_rank_info,
    increment_group_games_played,
    increment_group_games_won,
    record_group_correct_answer,
    record_group_wrong_answer,
)

# games
from .games import (
    create_game,
    finish_game,
    record_game_result,
)

# daily quiz
from .daily import (
    has_played_daily_quiz,
    record_daily_quiz_attempt,
)


__all__ = [
    # connection
    "get_conn",
    "create_tables",

    # players
    "ensure_player",
    "get_player",
    "add_points",
    "add_manual_points",
    "record_correct_answer",
    "record_wrong_answer",
    "increment_games_played",
    "increment_games_won",
    "get_top_players",
    "get_global_leaderboard",
    "get_global_leaderboard_page",
    "get_player_rank",
    "get_player_profile",
    "get_player_global_rank_info",
    "get_daily_leaderboard_page",
    "get_weekly_leaderboard_page",
    "get_monthly_leaderboard_page",
    "get_player_daily_rank_info",
    "get_player_weekly_rank_info",
    "get_player_monthly_rank_info",
    "get_all_user_ids",
    "get_total_players",
    "get_total_users_count",

    # 🔥 NEW FEATURES
    "get_player_stats",
    "get_player_full_profile",
    "has_claimed_daily_reward",
    "get_daily_reward_status",
    "claim_daily_reward",
    "reset_daily_streak_if_missed",
    "get_player_streak_info",

    # chats
    "ensure_chat",
    "deactivate_chat",

    # questions
    "add_question",
    "question_exists",
    "get_all_questions",
    "get_question_by_id",
    "update_question",
    "delete_question",
    "activate_question",
    "deactivate_question",
    "search_questions_by_keyword",
    "export_questions_to_rows",

    # groups
    "add_group_points",
    "get_group_leaderboard",
    "get_player_group_rank_info",
    "increment_group_games_played",
    "increment_group_games_won",
    "record_group_correct_answer",
    "record_group_wrong_answer",

    # games
    "create_game",
    "finish_game",
    "record_game_result",

    # daily quiz
    "has_played_daily_quiz",
    "record_daily_quiz_attempt",
]