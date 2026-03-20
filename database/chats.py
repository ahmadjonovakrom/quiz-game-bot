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