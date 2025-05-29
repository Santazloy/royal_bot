# handlers/ai.py

import os
import asyncio
import openai

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from utils.bot_utils import safe_answer

router = Router()

@router.message(Command("ai"))
async def cmd_ai(message: Message):
    """
    Команда /ai — выводит список доступных моделей OpenAI.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        await safe_answer(message, "❌ OpenAI API key is not set.")
        return

    # Функция получения моделей (будет выполнена в пуле потоков)
    def list_models():
        openai.api_key = api_key
        resp = openai.Model.list()
        return [m.id for m in resp.data]

    try:
        models = await asyncio.to_thread(list_models)
        if not models:
            await safe_answer(message, "⚠️ Не найдено доступных моделей.")
        else:
            text = "\n".join(models)
            await safe_answer(message, f"✅ Доступні моделі OpenAI:\n{text}")
    except Exception as e:
        await safe_answer(message, f"🚨 Помилка при отриманні моделей: {e}")
