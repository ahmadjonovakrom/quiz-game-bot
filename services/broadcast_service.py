from database import get_broadcast_chat_ids


async def broadcast_copied_message_service(bot, source_chat_id: int, source_message_id: int):
    chat_ids = get_broadcast_chat_ids()
    success = 0
    failed = 0

    for chat_id in chat_ids:
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source_chat_id,
                message_id=source_message_id,
            )
            success += 1
        except Exception:
            failed += 1

    return {
        "ok": True,
        "total": len(chat_ids),
        "success": success,
        "failed": failed,
    }