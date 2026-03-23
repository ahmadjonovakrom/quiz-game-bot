from .connection import get_conn


def save_bot_group_invite(chat_id: int, inviter_user_id: int):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO bot_group_invites (chat_id, inviter_user_id)
            VALUES (?, ?)
            """,
            (chat_id, inviter_user_id),
        )
        conn.commit()


def get_inviter_for_group(chat_id: int):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT inviter_user_id
            FROM bot_group_invites
            WHERE chat_id = ?
            """,
            (chat_id,),
        ).fetchone()
        return row["inviter_user_id"] if row else None


def has_claimed_group_bonus(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT claimed
            FROM group_bonus_claims
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        return bool(row and row["claimed"] == 1)


def mark_group_bonus_claimed(user_id: int, chat_id: int):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO group_bonus_claims (
                user_id, claimed, claimed_chat_id
            )
            VALUES (?, 1, ?)
            """,
            (user_id, chat_id),
        )
        conn.commit()