# handlers/embedding/openai_utils.py

import openai
import asyncio
import logging
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY
logger = logging.getLogger(__name__)


async def get_embedding(text: str) -> list[float]:
    """
    Возвращает эмбеддинг OpenAI для заданного текста.
    """
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: openai.Embedding.create(
                model="text-embedding-3-large",
                input=text
            )
        )
        return response["data"][0]["embedding"]
    except Exception as e:
        logger.error(f"[OpenAI] Ошибка при получении эмбеддинга: {e}")
        return []


async def transcribe_audio(file_path: str) -> str:
    """
    Расшифровка голосового файла (Whisper). Возвращает текст или пустую строку.
    """
    loop = asyncio.get_event_loop()
    try:
        with open(file_path, "rb") as audio_file:
            response = await loop.run_in_executor(
                None,
                lambda: openai.Audio.transcribe("whisper-1", audio_file)
            )
        return response["text"]
    except Exception as e:
        logger.error(f"[OpenAI] Ошибка при расшифровке аудио: {e}")
        return ""


async def generate_text(prompt: str, model="gpt-4o", max_tokens=2000) -> str:
    """
    Пример использования openai.Completion, если нужна простая генерация текста.
    """
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: openai.Completion.create(
                model=model,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=0.7,
                top_p=1.0
            )
        )
        return response.choices[0].text.strip()
    except Exception as e:
        logger.error(f"[OpenAI] Ошибка при генерации текста: {e}")
        return "Ошибка при генерации ответа."


async def generate_analysis_text(prompt: str) -> str:
    """
    Используем openai.ChatCompletion, чтобы сформировать «глубокий анализ» (daily_report).
    """
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.7
            )
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[OpenAI] Ошибка при получении анализа: {e}")
        return ""
