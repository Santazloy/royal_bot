# handlers/file.py

from __future__ import annotations

import asyncio
import logging
from typing import Final

from aiogram import Router, F, Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router(name="file_router")

# ───── разрешённые группы ─────
_ALLOWED_CHATS: Final[frozenset[int]] = frozenset((
    -1002503654146,   # Royal_1
    -1002569987326,   # Royal_2
    -1002699377044,   # Royal_3
    -1002696765874,   # Royal_4
    -1002555587028,   # Royal_5
    -1002525751059,   # Royal_6
))

# ───── исключённые пользователи ─────
EXCLUDED_USER_IDS: Final[frozenset[int]] = frozenset((
    7935161063,
    7281089930,
    1720928807,
    7894353415,
))

FILE_GROUP_ID: Final[int] = -1002260563352
TTL_SECONDS:   Final[int] = 180  # 3 минуты


# ────────────────────────────────────── helpers ──────────────────────────────────────
async def _delete_after(bot: Bot, chat_id: int, msg_id: int, delay: int = TTL_SECONDS):
    try:
        await asyncio.sleep(delay)
        await bot.delete_message(chat_id, msg_id)
    except Exception as e:
        logger.debug("Delete failed %s/%s: %s", chat_id, msg_id, e)


def _schedule_deletion(bot: Bot, chat_id: int, msg_id: int):
    asyncio.create_task(_delete_after(bot, chat_id, msg_id))


# ───────────────────────────────────── handler ───────────────────────────────────────
@router.message(
    F.chat.id.in_(_ALLOWED_CHATS),                  # только нужные группы
    F.photo,                                        # только фото-сообщения
)
async def handle_group_photo(message: Message, bot: Bot):
    uid     = message.from_user.id
    chat_id = message.chat.id
    msg_id  = message.message_id

    # — Фото от админ-UID → удалить через TTL
    if uid in EXCLUDED_USER_IDS:
        _schedule_deletion(bot, chat_id, msg_id)
        return

    # — Фото от остальных → копируем в FILE_GROUP_ID
    try:
        copy = await bot.copy_message(
            chat_id=FILE_GROUP_ID,
            from_chat_id=chat_id,
            message_id=msg_id,
        )
        # удалить копию
        _schedule_deletion(bot, FILE_GROUP_ID, copy.message_id)
    except Exception as e:
        logger.warning("Copy to file-group failed: %s", e)

    # удалить оригинал
    _schedule_deletion(bot, chat_id, msg_id)
