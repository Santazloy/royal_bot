# utils/bot_utils.py
from aiogram.types import Message, CallbackQuery
from aiogram.types.input_file import FSInputFile
import os

last_bot_message: dict[int, int] = {}

async def safe_answer(entity: Message | CallbackQuery, text: str = None, **kwargs):
    # Определяем chat_id и объект bot
    if hasattr(entity, "message") and hasattr(entity.message, "chat"):
        chat_id = entity.message.chat.id
        bot = entity.message.bot
    else:
        chat_id = entity.chat.id
        bot = entity.bot

    # Удаляем предыдущее сообщение
    prev = last_bot_message.get(chat_id)
    if prev:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=prev)
        except:
            pass

    sent = None

    # Отправка фото
    if "photo" in kwargs:
        photo = kwargs.pop("photo")
        caption = kwargs.pop("caption", text)
        # Преобразуем локальный путь в FSInputFile
        if isinstance(photo, str) and os.path.exists(photo):
            photo = FSInputFile(photo)
        sent = await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            **kwargs
        )
    else:
        # Обычный текст
        if hasattr(entity, "message") and hasattr(entity.message, "answer"):
            sent = await entity.message.answer(text, **kwargs)
        else:
            sent = await entity.answer(text, **kwargs)

    if sent is not None and hasattr(sent, "message_id"):
        last_bot_message[chat_id] = sent.message_id
    return sent
