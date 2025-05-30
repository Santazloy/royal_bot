from aiogram.types import Message, CallbackQuery
from aiogram.types.input_file import FSInputFile
from aiogram import Bot
import os

last_bot_message: dict[int, int] = {}

async def safe_answer(entity: Message | CallbackQuery, text: str = None, **kwargs):
    """
    Sends a message or photo, deleting the previous bot message in the chat if any.
    If kwargs contains 'photo', supports both file_id/URL and local file path (uses FSInputFile).
    """
    # Determine chat id
    if hasattr(entity, "message") and hasattr(entity.message, "chat"):
        chat_id = entity.message.chat.id
    else:
        chat_id = entity.chat.id

    # Delete previous bot message if exists
    prev = last_bot_message.get(chat_id)
    if prev:
        try:
            await entity.bot.delete_message(chat_id=chat_id, message_id=prev)
        except:
            pass

    # Send new message or photo
    if "photo" in kwargs:
        photo = kwargs.pop("photo")
        caption = kwargs.pop("caption", text)
        # Если photo - это путь к локальному файлу, используем FSInputFile
        if isinstance(photo, str) and os.path.exists(photo):
            photo = FSInputFile(photo)
        sent = await entity.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            **kwargs
        )
    else:
        # Standard text message
        if hasattr(entity, "message") and hasattr(entity.message, "answer"):
            sent = await entity.message.answer(text, **kwargs)
        else:
            sent = await entity.answer(text, **kwargs)

    last_bot_message[chat_id] = sent.message_id
    return sent
