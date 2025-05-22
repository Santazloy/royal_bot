# main.py

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import TELEGRAM_BOT_TOKEN
import db  # <--- инициализация пулa и создание таблиц

from handlers.news import router as news_router
from handlers.idphoto import router as idphoto_router
from handlers.group_id import router as group_id_router
from handlers.startemoji import router as startemoji_router
from handlers.booking.router import router as booking_router
from handlers.salary import salary_router
from handlers.menu import menu_router

# загрузчики состояния слотов и зарплат
from handlers.booking.loader import load_slots_from_db
from handlers.salary import load_salary_data_from_db
from handlers.clean import router as clean_router
async def main():
    logging.basicConfig(level=logging.INFO)

    # 1) Инициализируем пул
    await db.init_db_pool()

    # 2) Создаём таблицы
    await db.create_tables()

    # 3) Загружаем в память из БД:
    #    – брони и статусы для booking
    #    – опции salary, суммы и message_id для salary
    await load_slots_from_db()
    logging.info("Слоты и статусы загружены из БД в память.")
    await load_salary_data_from_db()
    logging.info("Настройки salary загружены из БД.")

    # 4) Инициализируем бота и диспетчер
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    # 5) Подключаем все роутеры
    dp.include_router(group_id_router)
    dp.include_router(news_router)
    dp.include_router(idphoto_router)
    dp.include_router(startemoji_router)
    dp.include_router(booking_router)
    dp.include_router(salary_router)
    dp.include_router(menu_router)
    dp.include_router(clean_router)

    # 6) Устанавливаем команды (для автодополнения в клиенте)
    await bot.set_my_commands([
        BotCommand(command="/start",  description="Начать"),
        BotCommand(command="/help",   description="Помощь"),
        BotCommand(command="/added",  description="Управление новостями"),
        BotCommand(command="/news",   description="Показать новости"),
        BotCommand(command="/id",     description="Получить file_id фото"),
        BotCommand(command="/emoji",  description="Смена эмоджи (только для админа)"),
        BotCommand(command="/book",   description="Забронировать слот"),
        BotCommand(command="/salary", description="Настроить salary (админ)"),
    ])

    # 7) Запускаем polling
    try:
        await dp.start_polling(bot)
    finally:
        # 8) Закрываем пул соединений
        await db.close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())
