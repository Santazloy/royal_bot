from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

@router.message(Command("id"))
async def cmd_id_photo(message: Message):
    # Проверяем, есть ли фото в сообщении
    if message.photo:
        # Берём file_id у самой большой (последней) версии фото
        largest_photo = message.photo[-1]
        await message.answer(f"file_id вашего фото:\n<code>{largest_photo.file_id}</code>",
                             parse_mode="HTML")
    else:
        await message.answer("Вы не прикрепили фото к команде /id.")