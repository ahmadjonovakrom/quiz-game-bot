# services/profile_service.py

from database.players import (
    get_top_players,
    get_player_profile,
    get_player_global_rank_info,
    get_daily_leaderboard_page,
    get_weekly_leaderboard_page,
    get_monthly_leaderboard_page,
)
from database.stats import (
    get_group_top_players,
    get_group_user_rank,
)


def safe_get(row, key, default=None):
    if row is None:
        return default
    try:
        return row[key]
    except Exception:
        if isinstance(row, dict):
            return row.get(key, default)
        return default


def extract_name(row) -> str:
    return (
        safe_get(row, "full_name")
        or safe_get(row, "name")
        or safe_get(row, "username")
        or "Unknown"
    )


def format_leaderboard_text(title: str, rows, points_key: str) -> str:
    if not rows:
        return f"🏆 {title}\n\nNo players yet."

    lines = [f"🏆 {title}", ""]

    for index, row in enumerate(rows, start=1):
        if index == 1:
            prefix = "🥇"
        elif index == 2:
            prefix = "🥈"
        elif index == 3:
            prefix = "🥉"
        else:
            prefix = f"{index}."

        name = extract_name(row)
        points = safe_get(row, points_key, 0)
        lines.append(f"{prefix} {name} — {points} pts")

    return "\n".join(lines)


def build_profile_text(user, profile_data, rank) -> str:
    if not profile_data:
        return (
            "👤 My Profile\n\n"
            f"Name: {user.full_name}\n"
            "Global Rank: Not ranked yet\n"
            "Points: 0\n"
            "Games Played: 0\n"
            "Correct Answers: 0"
        )

    full_name, username, total_points, games_played, correct_answers = profile_data

    lines = [
        "👤 My Profile",
        "",
        f"Name: {full_name}",
    ]

    if username:
        lines.append(f"Username: @{username}")

    lines.extend([
        f"Global Rank: #{rank}" if rank else "Global Rank: Not ranked yet",
        f"Points: {total_points}",
        f"Games Played: {games_played}",
        f"Correct Answers: {correct_answers}",
    ])

    return "\n".join(lines)


def get_profile_text_for_user(user_id: int, user) -> str:
    profile_data, rank = get_player_profile(user_id)
    return build_profile_text(user, profile_data, rank)


def get_global_leaderboard_text(limit: int = 10, offset: int = 0) -> str:
    rows = get_top_players(limit=limit)
    return format_leaderboard_text(
        "All-Time Leaderboard",
        rows,
        points_key="total_points",
    )


def get_group_leaderboard_text(chat_id: int, limit: int = 10, offset: int = 0) -> str:
    rows = get_group_top_players(chat_id, limit=limit)
    return format_leaderboard_text(
        "This Group Leaderboard",
        rows,
        points_key="points",
    )


def get_daily_leaderboard_text(limit: int = 10, offset: int = 0) -> str:
    rows = get_daily_leaderboard_page(limit=limit, offset=offset)
    return format_leaderboard_text(
        "Daily Leaderboard",
        rows,
        points_key="period_points",
    )


def get_weekly_leaderboard_text(limit: int = 10, offset: int = 0) -> str:
    rows = get_weekly_leaderboard_page(limit=limit, offset=offset)
    return format_leaderboard_text(
        "Weekly Leaderboard",
        rows,
        points_key="period_points",
    )


def get_monthly_leaderboard_text(limit: int = 10, offset: int = 0) -> str:
    rows = get_monthly_leaderboard_page(limit=limit, offset=offset)
    return format_leaderboard_text(
        "Monthly Leaderboard",
        rows,
        points_key="period_points",
    )


def get_global_rank_text(user_id: int, full_name: str) -> str:
    rank, points = get_player_global_rank_info(user_id)
    title = "My Global Rank"

    if not rank:
        return f"📊 {title}\n\nYou are not ranked yet."

    return (
        f"📊 {title}\n\n"
        f"Name: {full_name}\n"
        f"Rank: #{rank}\n"
        f"Points: {points}"
    )


def get_group_rank_text(chat_id: int, user_id: int, full_name: str) -> str:
    rank_data = get_group_user_rank(chat_id, user_id)
    title = "My Rank in This Group"

    if not rank_data:
        return f"📊 {title}\n\nYou are not ranked yet."

    return (
        f"📊 {title}\n\n"
        f"Name: {full_name}\n"
        f"Rank: #{rank_data['rank']}\n"
        f"Points: {rank_data['points']}"
    )