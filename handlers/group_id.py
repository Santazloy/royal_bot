# handlers/group_id.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from utils.bot_utils import safe_answer

router = Router()

@router.message(Command("chat"))
async def show_group_id(message: Message):
    """
    По команде /chat отправляет в чат его ID.
    """
    chat_id = message.chat.id
    await safe_answer(message, f"{chat_id}")

@router.callback_query(F.data == "chat_id")
async def callback_chat_id(query: CallbackQuery):
    """
    Кнопка 💬ChatID из меню /set: отвечает ID текущего чата.
    """
    await safe_answer(query, f"{query.message.chat.id}")
