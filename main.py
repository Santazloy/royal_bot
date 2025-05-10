# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import TELEGRAM_BOT_TOKEN
import db  # <--- импортируем модуль db целиком

from handlers.news import router as news_router
from handlers.idphoto import router as idphoto_router
from handlers.group_id import router as group_id_router
from handlers.startemoji import router as startemoji_router

async def main():
    logging.basicConfig(level=logging.INFO)

    # 1) Инициализируем пул
    await db.init_db_pool()
    # 2) Создаём таблицы
    await db.create_tables()

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(news_router)
    dp.include_router(idphoto_router)
    dp.include_router(group_id_router)
    dp.include_router(startemoji_router)

    # Устанавливаем команды
    await bot.set_my_commands([
        BotCommand(command="/start", description="Начать"),
        BotCommand(command="/help", description="Помощь"),
        BotCommand(command="/added", description="Управление новостями"),
        BotCommand(command="/news", description="Показать новости"),
        BotCommand(command="/id", description="Получить file_id фото"),
        BotCommand(command="/emoji", description="Смена эмоджи (только для админа)")
    ])

    try:
        await dp.start_polling(bot)
    finally:
        await db.close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())