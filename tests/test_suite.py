# tests/test_suite.py

import asyncio
import pytest
import logging
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, Chat, User
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

# ─────────────────────────────────────────────────────────────────────────────
#                Мок-классы для имитации Message/CallbackQuery
# ─────────────────────────────────────────────────────────────────────────────

class DummyMessage(Message):
    def __init__(self, chat_id: int, bot: Bot):
        # Chat и bot нужны, чтобы safe_answer мог их использовать
        self.chat = Chat(chat_id, "testchat")
        self.bot = bot
        self.message_id = None
        self.text = None  # Для модуля конвертера

    async def answer(self, text=None, **kwargs):
        # Симулируем отправку сообщения; возвращаем объект с message_id
        class Sent:
            pass
        sent = Sent()
        sent.message_id = 999
        return sent

class DummyCallback(CallbackQuery):
    def __init__(self, message: DummyMessage):
        # В CallbackQuery поля .message и .from_user должны быть заполнены
        self.message = message
        self.from_user = User(id=message.chat.id, is_bot=False, first_name="User")
        self.data = None

    async def answer(self, show_alert=False):
        # «Ответ» на нажатие кнопки
        return
