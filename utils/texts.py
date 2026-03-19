def admin_only_text() -> str:
    return "❌ Admin only."


def medal(rank_number: int) -> str:
    if rank_number == 1:
        return "🥇"
    if rank_number == 2:
        return "🥈"
    if rank_number == 3:
        return "🥉"
    return f"{rank_number}."


def status_text(is_active: int) -> str:
    return "✅ Active" if is_active else "🚫 Inactive"


def display_name_from_row(row) -> str:
    if row["username"]:
        return f"@{row['username']}"
    return row["full_name"] or f"User {row['user_id']}"


def format_leaderboard_menu_text() -> str:
    return "🏆 Leaderboard\n\nChoose a view:"


def format_leaderboard_text(title: str, rows, offset: int, my_rank, my_points) -> str:
    lines = [title, ""]

    for i, row in enumerate(rows, start=offset + 1):
        name = display_name_from_row(row)
        lines.append(f"{medal(i)} {name} — {row['total_points']}")

    lines.extend([
        "",
        "━━━━━━━━━━━━",
        f"Your rank: #{my_rank if my_rank else '-'}",
        f"Your points: {my_points}",
    ])

    return "\n".join(lines)


def format_profile_text(player, global_rank, chat_type: str, group_rank=None, group_points=None) -> str:
    if not player:
        return "👤 Player Profile\n\nNo profile data yet."

    display_name = f"@{player['username']}" if player["username"] else player["full_name"]
    fastest = player["fastest_answer_time"]
    fastest_text = f"{fastest:.2f}s" if fastest is not None else "—"

    lines = [
        "👤 Player Profile",
        "",
        f"Name: {display_name}",
        "",
        f"🎮 Games: {player['games_played']}",
        f"🏆 Wins: {player['games_won']}",
        f"✅ Correct: {player['correct_answers']}",
        f"❌ Wrong: {player['wrong_answers']}",
        f"🔥 Best streak: {player['best_streak']}",
        f"⭐ Points: {player['total_points']}",
        f"⚡ Fastest answer: {fastest_text}",
        f"🌍 Global rank: #{global_rank if global_rank else '-'}",
    ]

    if chat_type in ("group", "supergroup"):
        lines.extend([
            f"👥 Group rank: #{group_rank if group_rank else '-'}",
            f"👥 Group points: {group_points}",
        ])

    return "\n".join(lines)


def format_my_rank_text(global_rank, global_points, chat_type: str, group_rank=None, group_points=None) -> str:
    lines = [
        "🪪 My Rank",
        "",
        f"🌍 Global rank: #{global_rank if global_rank else '-'}",
        f"⭐ Points: {global_points}",
    ]

    if chat_type != "private":
        lines.extend([
            "",
            f"👥 Group rank: #{group_rank if group_rank else '-'}",
            f"👥 Group points: {group_points}",
        ])

    return "\n".join(lines)


def format_admin_panel_text() -> str:
    return "🛠 Admin Panel\n\nChoose an action:"


def format_questions_menu_text() -> str:
    return "📚 Questions\n\nChoose an action:"


def format_question_preview(q: tuple) -> str:
    question_id = q[0]
    question_text = q[1]
    option_a = q[2]
    option_b = q[3]
    option_c = q[4]
    option_d = q[5]
    correct_letter = q[6]
    category = q[7]
    difficulty = q[8]
    is_active = q[9]
    times_used = q[10]

    return (
        f"📘 Question #{question_id}\n\n"
        f"Status: {status_text(is_active)}\n"
        f"Category: {category.title()}\n"
        f"Difficulty: {difficulty.title()}\n"
        f"Times used: {times_used}\n\n"
        f"❓ {question_text}\n\n"
        f"A) {option_a}\n"
        f"B) {option_b}\n"
        f"C) {option_c}\n"
        f"D) {option_d}\n\n"
        f"✅ Correct answer: {correct_letter}"
    )


def format_question_details_text(q: tuple) -> str:
    return format_question_preview(q)


def format_search_results_text(keyword: str, results) -> str:
    if not results:
        return f"🔎 Search Results\n\nKeyword: {keyword}\n\nNo questions found."

    lines = [
        "🔎 Search Results",
        "",
        f"Keyword: {keyword}",
        "",
    ]

    for q in results:
        qid = q[0]
        question_text = q[1]
        category = q[7]
        difficulty = q[8]
        is_active = q[9]

        short_question = question_text[:55] + "..." if len(question_text) > 55 else question_text
        lines.append(
            f"{status_text(is_active)} | ID {qid}\n"
            f"{short_question}\n"
            f"📚 {category} • {difficulty}"
        )
        lines.append("")

    return "\n".join(lines).strip()


def format_latest_questions_text(questions) -> str:
    if not questions:
        return "📋 Latest Questions\n\nNo questions found."

    lines = ["📋 Latest Questions", ""]

    for q in questions:
        qid = q[0]
        question_text = q[1]
        category = q[7]
        difficulty = q[8]
        is_active = q[9]

        short_question = question_text[:45] + "..." if len(question_text) > 45 else question_text

        lines.append(
            f"{status_text(is_active)} | ID {qid}\n"
            f"{short_question}\n"
            f"📚 {category} • {difficulty}"
        )
        lines.append("")

    return "\n".join(lines).strip()


def format_bot_stats_text(stats: dict) -> str:
    return (
        "📊 Stats\n\n"
        f"👥 Users: {stats['total_users']}\n"
        f"👨‍👩‍👧‍👦 Groups: {stats['total_groups']}\n"
        f"🎮 Games: {stats['total_games']}\n"
        f"❓ Questions: {stats['total_questions']}"
    )


def format_import_help_text(categories, difficulties) -> str:
    return (
        "📥 Import CSV\n\n"
        "Send a CSV file with this header:\n\n"
        "question_text,option_a,option_b,option_c,option_d,correct_option,category,difficulty\n\n"
        "Example:\n"
        "What does rapid mean?,slow,fast,weak,late,B,vocabulary,easy\n\n"
        "Allowed correct_option:\n"
        "A / B / C / D or 1 / 2 / 3 / 4\n\n"
        "Allowed categories:\n"
        f"{', '.join(categories)}\n\n"
        "Allowed difficulties:\n"
        f"{', '.join(difficulties)}\n\n"
        "Empty category → mixed\n"
        "Empty difficulty → easy"
    )