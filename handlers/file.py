from __future__ import annotations

import asyncio
import logging
from typing import Final

from aiogram import Router, F, Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router(name="file_router")

# ───── настройки ─────
EXCLUDED_USER_IDS: Final[set[int]] = {
    7935161063,
    7281089930,
    1720928807,
    7894353415,
}
FILE_GROUP_ID: Final[int] = -1002260563352          # целевая «группа-файлов»
TTL_SECONDS: Final[int] = 180                      # 3 минуты


async def _delete_later(bot: Bot, chat_id: int, msg_id: int, delay: int = TTL_SECONDS):
    """Удалить сообщение через delay секунд, игнорируем ошибки."""
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id, msg_id)
    except Exception as e:
        logger.debug("Cannot delete %s/%s: %s", chat_id, msg_id, e)


@router.message(
    F.photo,
    F.chat.type.in_({"group", "supergroup"}),        # только групповые чаты
)
async def handle_group_photo(message: Message, bot: Bot):
    """
    • Фото от UID из EXCLUDED_USER_IDS → просто удалить через 3 мин.
    • Фото от остальных:
        1) копия в FILE_GROUP_ID;
        2) оригинал удалить через 3 мин.;
        3) копию в FILE_GROUP_ID удалить через 3 мин.
    """
    uid = message.from_user.id

    if uid in EXCLUDED_USER_IDS:
        asyncio.create_task(_delete_later(bot, message.chat.id, message.message_id))
        return

    # пересылаем/копируем в FILE_GROUP_ID
    try:
        sent = await bot.copy_message(
            chat_id=FILE_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        # удалить копию в файловой группе
        asyncio.create_task(_delete_later(bot, FILE_GROUP_ID, sent.message_id))
    except Exception as e:
        logger.warning("Cannot copy photo to file-group: %s", e)

    # удалить оригинал в исходной группе
    asyncio.create_task(_delete_later(bot, message.chat.id, message.message_id))
