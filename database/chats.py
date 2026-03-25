from contextlib import closing

from .connection import get_conn


def ensure_chat(chat) -> None:
    chat_id = chat.id
    chat_type = chat.type
    title = getattr(chat, "title", None) or ""
    username = getattr(chat, "username", None) or ""

    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            "SELECT chat_id FROM chats WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()

        if row:
            conn.execute("""
                UPDATE chats
                SET chat_type = ?,
                    title = ?,
                    username = ?,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE chat_id = ?
            """, (chat_type, title, username, chat_id))
        else:
            conn.execute("""
                INSERT INTO chats (
                    chat_id, chat_type, title, username, is_active, updated_at
                ) VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            """, (chat_id, chat_type, title, username))


def deactivate_chat(chat_id: int) -> None:
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            UPDATE chats
            SET is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE chat_id = ?
        """, (chat_id,))


def get_all_groups():
    with closing(get_conn()) as conn:
        return conn.execute("""
            SELECT
                chat_id,
                chat_type,
                title,
                username,
                is_active,
                updated_at
            FROM chats
            WHERE chat_type IN ('group', 'supergroup')
            ORDER BY
                CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
                COALESCE(NULLIF(title, ''), username, CAST(chat_id AS TEXT)) COLLATE NOCASE
        """).fetchall()


def get_group_stats(chat_id: int):
    with closing(get_conn()) as conn:
        chat_row = conn.execute("""
            SELECT
                chat_id,
                chat_type,
                title,
                username,
                is_active,
                updated_at
            FROM chats
            WHERE chat_id = ?
        """, (chat_id,)).fetchone()

        players_row = conn.execute("""
            SELECT COUNT(*) AS player_count
            FROM group_scores
            WHERE chat_id = ?
        """, (chat_id,)).fetchone()

        games_row = conn.execute("""
            SELECT COUNT(*) AS game_count
            FROM games
            WHERE chat_id = ?
        """, (chat_id,)).fetchone()

        return {
            "chat": chat_row,
            "player_count": players_row["player_count"] if players_row else 0,
            "game_count": games_row["game_count"] if games_row else 0,
        }