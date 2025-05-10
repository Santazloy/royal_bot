# handlers/group_id.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

# Создаём свой роутер
router = Router()

@router.message(Command("chat"))
async def show_group_id(message: Message):
    """
    По команде /chat отправляет в чат его ID.
    """
    chat_id = message.chat.id
    await message.answer(f"{chat_id}")

@router.callback_query(F.data == "chat_id")
async def callback_chat_id(query: CallbackQuery):
    """
    Кнопка 💬ChatID из меню /set: отвечает ID текущего чата.
    """
    await query.message.answer(f"{query.message.chat.id}")
    await query.answer()