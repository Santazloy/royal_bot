# handlers/group_id.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from utils.bot_utils import safe_answer

router = Router()

@router.message(Command("chat"))
async def show_group_id(message: Message):
    chat_id = message.chat.id
    await safe_answer(message, text=f"{chat_id}")

@router.callback_query(F.data == "leonard_group_id")
async def callback_chat_id(query: CallbackQuery):
    await safe_answer(query, text=f"{query.message.chat.id}")
