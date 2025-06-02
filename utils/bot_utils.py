from __future__ import annotations

import os
from typing import Any, Mapping, Union, Optional

from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
)
from aiogram.types.input_file import FSInputFile

last_bot_message: dict[int, int] = {}


async def _send_photo(
    bot,
    chat_id: int,
    photo: Union[str, FSInputFile],
    caption: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Message:
    """
    Упрощённая обёртка вокруг bot.send_photo без лишних параметров.
    """
    if isinstance(photo, str) and os.path.exists(photo):
        photo = FSInputFile(photo)
    return await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        reply_markup=reply_markup,
    )


async def safe_answer(
    entity: Message | CallbackQuery,
    text: str | None = None,
    **kwargs: Mapping[str, Any],
):
    """
    Унифицированный ответ для Message и CallbackQuery.
    ▸ show_alert действует только на callback.answer.
    ▸ photo / caption передаются исключительно в bot.send_photo.
    """
    # ───── определить chat / bot ─────
    if isinstance(entity, CallbackQuery):
        chat_id = entity.message.chat.id
        bot     = entity.message.bot
    else:  # Message
        chat_id = entity.chat.id
        bot     = entity.bot

    # ───── callback.answer (если нужно) ─────
    show_alert: bool = bool(kwargs.pop("show_alert", False))
    if isinstance(entity, CallbackQuery):
        try:
            await entity.answer(show_alert=show_alert)
        except Exception:
            pass  # игнорируем возможные ошибки от повторного answer

    # ───── удалить предыдущий ответ бота ─────
    prev = last_bot_message.get(chat_id)
    if prev:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=prev)
        except Exception:
            pass

    sent: Optional[Message] = None

    # ───── отправка фото или текста ─────
    if "photo" in kwargs:
        photo        = kwargs.pop("photo")
        caption      = kwargs.pop("caption", text)
        reply_markup = kwargs.pop("reply_markup", None)
        sent = await _send_photo(bot, chat_id, photo, caption, reply_markup)
    else:
        reply_markup = kwargs.pop("reply_markup", None)
        if isinstance(entity, CallbackQuery):
            sent = await entity.message.answer(text or "", reply_markup=reply_markup, **kwargs)
        else:  # Message
            sent = await entity.answer(text or "", reply_markup=reply_markup, **kwargs)

    # ───── сохранить ID сообщения ─────
    if sent is not None and hasattr(sent, "message_id"):
        last_bot_message[chat_id] = sent.message_id
    return sent
