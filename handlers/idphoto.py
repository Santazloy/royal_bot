# handlers/idphoto.py

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

# Store last bot-sent message per chat
last_bot_message: dict[int, int] = {}

async def safe_answer(entity, text: str, **kwargs):
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

    # Send new message
    if hasattr(entity, "message") and hasattr(entity.message, "answer"):
        sent = await entity.message.answer(text, **kwargs)
    else:
        sent = await entity.answer(text, **kwargs)

    last_bot_message[chat_id] = sent.message_id
    return sent

@router.message(Command("id"))
async def cmd_id_photo(message: Message):
    # Проверяем, есть ли фото в сообщении
    if message.photo:
        # Берём file_id у самой большой (последней) версии фото
        largest_photo = message.photo[-1]
        await safe_answer(
            message,
            f"file_id вашего фото:\n<code>{largest_photo.file_id}</code>",
            parse_mode="HTML"
        )
    else:
        await safe_answer(
            message,
            "Вы не прикрепили фото к команде /id."
        )
