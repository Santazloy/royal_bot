# handlers/embedding/commands.py

import os
import logging

from aiogram import Router, types
from aiogram.filters.command import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, CallbackQuery

from config import VECTOR_GROUP_IDS
from handlers.embedding.reporting import (
    send_report_for_period,
    send_reports_for_all_groups
)
from handlers.embedding.openai_utils import get_embedding, transcribe_audio
from db import save_message, save_embedding, count_embeddings  # ваши функции для работы с БД

logger = logging.getLogger(__name__)
router = Router()

# Файл-картинка, который будем отправлять перед кнопками
COMMON_PHOTO_PATH = os.path.join(os.path.dirname(__file__), "../../photo/IMG_2585.JPG")


@router.message(Command("vector"))
async def cmd_vector(message: types.Message):
    """
    При команде /vector бот:
    1) Отправляет общее фото «photo/IMG_2585.JPG»
    2) Подставляет под ним клавиатуру с кнопками: Test, Report, Three, Week, Month
    """
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton(text="Test", callback_data="vector_test"),
        InlineKeyboardButton(text="Report", callback_data="vector_report"),
        InlineKeyboardButton(text="Three", callback_data="vector_three"),
        InlineKeyboardButton(text="Week", callback_data="vector_week"),
        InlineKeyboardButton(text="Month", callback_data="vector_month"),
    )

    # Пытаемся отправить картинку
    try:
        photo = FSInputFile(COMMON_PHOTO_PATH)
        await message.answer_photo(photo=photo, caption="Выберите действие:", reply_markup=kb)
    except FileNotFoundError:
        # Если картинки нет – просто отправляем текст и клавиатуру
        await message.answer("Выберите действие:", reply_markup=kb)


# --- CallbackQuery-хендлеры для кнопок ---
@router.callback_query(lambda c: c.data and c.data.startswith("vector_"))
async def vector_callback_handler(callback: CallbackQuery):
    """
    Обрабатываем нажатия на кнопки:
    - vector_test
    - vector_report
    - vector_three
    - vector_week
    - vector_month
    """
    data = callback.data
    chat_id = callback.message.chat.id
    bot = callback.bot

    # 1) Test: просто вернуть количество эмбеддингов
    if data == "vector_test":
        total = await count_embeddings()
        await bot.send_message(chat_id, f"Общее количество эмбеддингов в БД: {total}")
        await callback.answer()  # убираем «часики» у кнопки
        return

    # 2) Report: отчёт за 1 день
    if data == "vector_report":
        await send_report_for_period(bot, chat_id, days=1)
        await bot.send_message(chat_id, "Отчёт за 1 день сформирован.")
        await callback.answer()
        return

    # 3) Three: отчёт за 3 дня
    if data == "vector_three":
        await send_report_for_period(bot, chat_id, days=3)
        await bot.send_message(chat_id, "Отчёт за 3 дня сформирован.")
        await callback.answer()
        return

    # 4) Week: отчёт за 7 дней
    if data == "vector_week":
        await send_report_for_period(bot, chat_id, days=7)
        await bot.send_message(chat_id, "Отчёт за 7 дней сформирован.")
        await callback.answer()
        return

    # 5) Month: отчёт за 30 дней
    if data == "vector_month":
        await send_report_for_period(bot, chat_id, days=30)
        await bot.send_message(chat_id, "Отчёт за 30 дней сформирован.")
        await callback.answer()
        return

    # Если попало что-то неожиданное
    await callback.answer("Неизвестная команда.", show_alert=True)


# --- Хендлер текстовых сообщений: сохраняем в БД и эмбеддим ---
from aiogram import F
from handlers.embedding.openai_utils import get_embedding, transcribe_audio
from config import VECTOR_GROUP_IDS
from db import save_message, save_embedding   # функции должны быть в вашем db.py
from your_language_detector import detect_language_of_trigger  # предполагаемая утилита
from handlers.embedding.openai_utils import generate_text  # или generate_analysis_text

VOICE_TRIGGERS_EN = ["voice en", "speak en"]
VOICE_TRIGGERS_RU = ["voice ru", "speak ru"]

TEXT_TRIGGERS_EN = ["text en", "say en"]
TEXT_TRIGGERS_RU = ["text ru", "say ru"]


@router.message(F.text)
async def handle_text_message(message: types.Message):
    """
    1) Сохраняем текст в БД + эмбеддинг (если chat.id в VECTOR_GROUP_IDS)
    2) Проверяем триггеры:
       - Если есть голосовой триггер (RU или EN) => GPT + TTS
       - Если есть текстовый триггер (RU или EN) => GPT (только текст)
       - Иначе — просто сохраняем и выходим.
    """
    if message.chat.id not in VECTOR_GROUP_IDS:
        return

    text = message.text.strip()
    if not text:
        return

    user_name = message.from_user.full_name if message.from_user else "unknown"
    # 1) сохраняем текст в таблицу messages, на вашей стороне должна быть async-функция save_message
    await save_message(
        group_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else 0,
        user_name=user_name,
        text=text
    )

    # 2) Получаем эмбеддинг
    emb = await get_embedding(text)
    if emb:
        await save_embedding(message.chat.id, message.from_user.id if message.from_user else 0, emb)
        logger.info(f"Эмбеддинг для '{text}' сохранён.")
    else:
        logger.error(f"Ошибка эмбеддинга для '{text}'")
        return

    # 3) Проверяем триггеры на основе языка
    lang = detect_language_of_trigger(text)  # ваша функция-определитель языка
    text_lower = text.lower()

    # 3a) Если voice-trigger (EN или RU) — транскрипт + GPT + отправка голоса
    if any(t in text_lower for t in VOICE_TRIGGERS_EN + VOICE_TRIGGERS_RU):
        # сначала транскрибируем (если текст), здесь нет аудио, но мы эмулируем
        reply = await generate_text(text_lower, model="gpt-4o")
        # Тут можно отправить голосом через TTS-движок (не показано)
        await message.answer(f"[{lang.upper()}-TTS] {reply}")
        return

    # 3b) Если text-trigger (EN или RU) — GPT (только текст)
    if any(t in text_lower for t in TEXT_TRIGGERS_EN + TEXT_TRIGGERS_RU):
        reply = await generate_text(text_lower, model="gpt-4o")
        await message.answer(reply)
        return

    # Иначе — ничего более не делаем (либо просто сохраняем для аналитики)
    return


@router.message(F.voice)
async def handle_voice_message(message: types.Message):
    """
    1) Скачиваем voice -> temp_voice.ogg
    2) Расшифровываем (Whisper)
    3) Сохраняем транскрипт в БД + эмбеддинг
    """
    if message.chat.id not in VECTOR_GROUP_IDS:
        return

    bot = message.bot
    file_info = await bot.get_file(message.voice.file_id)
    local_filename = "temp_voice.ogg"
    await bot.download_file(file_info.file_path, local_filename)

    transcribed_text = await transcribe_audio(local_filename)
    if not transcribed_text:
        await message.answer("Не удалось распознать голосовое сообщение :(")
        return

    user_name = message.from_user.full_name if message.from_user else "unknown"
    await save_message(message.chat.id, message.from_user.id if message.from_user else 0, user_name, transcribed_text)

    emb = await get_embedding(transcribed_text)
    if emb:
        await save_embedding(message.chat.id, message.from_user.id if message.from_user else 0, emb)
        await message.answer(f"Распознанный текст:\n{transcribed_text}")
    else:
        await message.answer("Ошибка при получении эмбеддинга.")


# --- Дополнительные команды (запросы по кнопкам) ---

@router.message(Command("test"))
async def cmd_test(message: types.Message):
    total = await count_embeddings()
    await message.answer(f"Общее количество эмбеддингов в БД: {total}")


@router.message(Command("report"))
async def cmd_report(message: types.Message):
    bot = message.bot
    await send_report_for_period(bot, message.chat.id, days=1)
    await message.answer("Отчёт (за 1 день) сформирован.")


@router.message(Command("three"))
async def cmd_three(message: types.Message):
    bot = message.bot
    await send_report_for_period(bot, message.chat.id, days=3)
    await message.answer("Отчёт (за 3 дня) сформирован.")


@router.message(Command("week"))
async def cmd_week(message: types.Message):
    bot = message.bot
    await send_report_for_period(bot, message.chat.id, days=7)
    await message.answer("Отчёт (за 7 дней) сформирован.")


@router.message(Command("month"))
async def cmd_month(message: types.Message):
    bot = message.bot
    await send_report_for_period(bot, message.chat.id, days=30)
    await message.answer("Отчёт (за 30 дней) сформирован.")
