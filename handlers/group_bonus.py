import logging

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

from database import (
    save_bot_group_invite,
    get_inviter_for_group,
    has_claimed_group_bonus,
    mark_group_bonus_claimed,
    add_points,
)

logger = logging.getLogger(__name__)

GROUP_BONUS_POINTS = 1000


async def bot_added_to_group_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat_member_update = update.my_chat_member
    if not chat_member_update:
        return

    chat = chat_member_update.chat
    if chat.type not in ("group", "supergroup"):
        return

    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status
    inviter = chat_member_update.from_user

    was_absent = old_status in (
        ChatMemberStatus.LEFT,
        ChatMemberStatus.BANNED,
    )
    is_now_present = new_status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    )

    if was_absent and is_now_present and inviter:
        save_bot_group_invite(chat.id, inviter.id)
        logger.info(
            "Bot added to group %s by user %s",
            chat.id,
            inviter.id,
        )


async def bot_is_admin_in_group(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> bool:
    me = await context.bot.get_me()
    member = await context.bot.get_chat_member(chat_id, me.id)
    return member.status in (
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    )


async def try_give_group_bonus(
    chat_id: int,
    game: dict,
    context: ContextTypes.DEFAULT_TYPE,
):
    players = game.get("players", {})
    inviter_id = get_inviter_for_group(chat_id)

    if not inviter_id:
        return

    if inviter_id not in players:
        return

    if has_claimed_group_bonus(inviter_id):
        return

    if not await bot_is_admin_in_group(context, chat_id):
        return

    add_points(inviter_id, GROUP_BONUS_POINTS)
    mark_group_bonus_claimed(inviter_id, chat_id)

    try:
        await context.bot.send_message(
            chat_id=inviter_id,
            text="🎉 You earned +1000 🍋 for completing your first group game!",
        )
    except Exception:
        logger.exception("Failed to send group bonus message to %s", inviter_id)