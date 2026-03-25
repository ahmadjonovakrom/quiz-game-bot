def admin_only_text():
    return "❌ Admin only."


def format_admin_panel_text():
    return "\n".join([
        "🛠 Admin Panel",
        "",
        "Choose an action:",
    ])


def format_questions_menu_text():
    return "\n".join([
        "📚 Question Management",
        "",
        "Choose an action:",
    ])


def format_bot_stats_text(stats):
    users = stats.get("total_users", 0)
    players = stats.get("total_players", 0)
    questions = stats.get("total_questions", 0)
    games = stats.get("total_games", 0)
    groups = stats.get("total_groups", 0)

    return "\n".join([
        "📊 Bot Stats",
        "",
        f"👤 Users: {users}",
        f"🎮 Players: {players}",
        f"📚 Questions: {questions}",
        f"🕹 Games: {games}",
        f"👥 Groups: {groups}",
    ])

def format_groups_list_text(groups):
    if not groups:
        return "\n".join([
            "👥 Bot Groups",
            "",
            "No groups found.",
        ])

    return "\n".join([
        "👥 Bot Groups",
        "",
        "Choose a group below:",
    ])


def format_group_details_text(group_stats):
    chat = group_stats.get("chat")

    if not chat:
        return "\n".join([
            "👥 Group Info",
            "",
            "Group not found.",
        ])

    title = chat["title"] or "No title"
    username = f"@{chat['username']}" if chat["username"] else "—"
    status = "Active" if chat["is_active"] else "Inactive"
    game_count = group_stats.get("game_count", 0)
    player_count = group_stats.get("player_count", 0)

    return "\n".join([
        "👥 Group Info",
        "",
        f"🏷 Name: {title}",
        f"🆔 Chat ID: {chat['chat_id']}",
        f"🔗 Username: {username}",
        f"📌 Status: {status}",
        f"🕹 Games: {game_count}",
        f"🎮 Players: {player_count}",
    ])

def format_import_help_text(allowed_categories, allowed_difficulties):
    return "\n".join([
        "📥 Import Questions from CSV",
        "",
        "Expected CSV columns:",
        "question_text, option_a, option_b, option_c, option_d, correct_option, category, difficulty",
        "",
        f"Allowed categories: {', '.join(allowed_categories)}",
        f"Allowed difficulties: {', '.join(allowed_difficulties)}",
        "",
        "Send a .csv file to import questions.",
    ])


def format_question_preview(q):
    question_text = q[1]
    option_a = q[2]
    option_b = q[3]
    option_c = q[4]
    option_d = q[5]
    correct_option = q[6]
    category = q[7]
    difficulty = q[8]
    is_active = q[9] if len(q) > 9 else 1

    status = "Active" if is_active else "Disabled"

    return "\n".join([
        f"ID: {q[0]}",
        f"Question: {question_text}",
        f"A) {option_a}",
        f"B) {option_b}",
        f"C) {option_c}",
        f"D) {option_d}",
        f"Correct: {correct_option}",
        f"Category: {category}",
        f"Difficulty: {difficulty}",
        f"Status: {status}",
    ])


def format_question_details_text(q):
    times_used = q[10] if len(q) > 10 else 0

    return "\n".join([
        "📘 Question Details",
        "",
        format_question_preview(q),
        f"Times Used: {times_used}",
    ])


def format_latest_questions_text(questions):
    if not questions:
        return "\n".join([
            "📋 Latest Questions",
            "",
            "No questions found.",
        ])

    lines = [
        "📋 Latest Questions",
        "",
    ]

    for q in questions:
        qid = q[0]
        question_text = q[1]
        category = q[7] if len(q) > 7 else "mixed"
        difficulty = q[8] if len(q) > 8 else "easy"
        is_active = q[9] if len(q) > 9 else 1
        status = "✅" if is_active else "🚫"

        short_text = question_text if len(question_text) <= 80 else question_text[:77] + "..."

        lines.append(f"{status} #{qid} [{category}/{difficulty}]")
        lines.append(short_text)
        lines.append("")

    return "\n".join(lines).strip()


def format_search_results_text(keyword, results):
    if not results:
        return "\n".join([
            "🔎 Search Results",
            "",
            f"Keyword: {keyword}",
            "",
            "No matching questions found.",
        ])

    lines = [
        "🔎 Search Results",
        "",
        f"Keyword: {keyword}",
        f"Found: {len(results)}",
        "",
    ]

    for q in results:
        qid = q[0]
        question_text = q[1]
        category = q[7] if len(q) > 7 else "mixed"
        difficulty = q[8] if len(q) > 8 else "easy"
        is_active = q[9] if len(q) > 9 else 1
        status = "✅" if is_active else "🚫"

        short_text = question_text if len(question_text) <= 70 else question_text[:67] + "..."
        lines.append(f"{status} #{qid} [{category}/{difficulty}] {short_text}")

    return "\n".join(lines)


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