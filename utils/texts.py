def admin_only_text():
    return "❌ Admin only."


def format_profile_text(player, global_rank, chat_type, group_rank=None, group_points=None):
    if not player:
        return "No profile data found yet."

    full_name = player["full_name"] or "Unknown"
    username = f"@{player['username']}" if player["username"] else "—"
    total_points = player["total_points"] or 0
    games_played = player["games_played"] or 0
    games_won = player["games_won"] or 0
    correct_answers = player["correct_answers"] or 0
    wrong_answers = player["wrong_answers"] or 0
    best_streak = player["best_streak"] or 0
    fastest_answer = player["fastest_answer_time"]

    accuracy = 0
    total_answers = correct_answers + wrong_answers
    if total_answers > 0:
        accuracy = round((correct_answers / total_answers) * 100)

    fastest_answer_text = f"{fastest_answer:.2f}s" if fastest_answer is not None else "—"

    lines = [
        "👤 Your Profile",
        "",
        f"Name: {full_name}",
        f"Username: {username}",
        "",
        f"🏆 Total Points: {total_points}",
        f"🎮 Games Played: {games_played}",
        f"🥇 Games Won: {games_won}",
        f"✅ Correct Answers: {correct_answers}",
        f"❌ Wrong Answers: {wrong_answers}",
        f"🎯 Accuracy: {accuracy}%",
        f"🔥 Best Streak: {best_streak}",
        f"⚡ Fastest Answer: {fastest_answer_text}",
        "",
        f"🌍 Global Rank: #{global_rank}" if global_rank else "🌍 Global Rank: Unranked",
    ]

    if chat_type in ("group", "supergroup"):
        if group_rank:
            lines.append(f"👥 Group Rank: #{group_rank}")
            lines.append(f"🏅 Group Points: {group_points or 0}")
        else:
            lines.append("👥 Group Rank: Unranked")
            lines.append(f"🏅 Group Points: {group_points or 0}")

    return "\n".join(lines)


def format_leaderboard_menu_text():
    return "\n".join([
        "🏆 Leaderboards",
        "",
        "Choose a leaderboard:",
    ])


def format_leaderboard_text(title, rows, offset, my_rank, my_points):
    lines = [title, ""]

    if not rows:
        lines.append("No players yet.")
    else:
        for i, row in enumerate(rows, start=offset + 1):
            name = row["full_name"] or row["username"] or f"User {row['user_id']}"
            points = row["period_points"] if "period_points" in row.keys() else row["total_points"]
            lines.append(f"{i}. {name} — {points} pts")

    if my_rank:
        lines.append("")
        lines.append(f"🪪 Your rank: #{my_rank} — {my_points} pts")

    return "\n".join(lines)


def format_my_rank_text(global_rank, global_points, chat_type, group_rank=None, group_points=None):
    lines = [
        "🪪 My Rank",
        "",
        f"🌍 Global Rank: #{global_rank} — {global_points} pts" if global_rank else "🌍 Global Rank: Unranked",
    ]

    if chat_type != "private":
        if group_rank:
            lines.append(f"👥 Group Rank: #{group_rank} — {group_points} pts")
        else:
            lines.append("👥 Group Rank: Unranked")

    return "\n".join(lines)