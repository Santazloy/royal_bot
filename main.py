# main.py

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import TELEGRAM_BOT_TOKEN
import db  # init пулa и создание таблиц

# загрузчики состояния зарплат


# роутеры
from handlers.group_id import router as group_id_router
from handlers.news import router as news_router
from handlers.idphoto import router as idphoto_router
from handlers.startemoji import router as startemoji_router
from handlers.booking.router import router as booking_router
from handlers.salary import salary_router, load_salary_data_from_db
from handlers.menu import menu_router
from handlers.clean import router as clean_router

# единый репозиторий для бронирования
from db_access.booking_repo import BookingRepo

async def main():
    logging.basicConfig(level=logging.INFO)

    # 1) Инициализируем пул и создаём таблицы
    await db.init_db_pool()
    await db.create_tables()

    # 2) Загружаем все брони/статусы в память
    repo = BookingRepo(db.db_pool)
    await repo.load_data()
    logging.info("Слоты и статусы загружены из БД.")

    # 3) Загружаем настройки salary
    await load_salary_data_from_db()
    logging.info("Настройки salary загружены из БД.")

    # 4) Настраиваем бота
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    # 5) Регистрируем роутеры
    dp.include_router(group_id_router)
    dp.include_router(news_router)
    dp.include_router(idphoto_router)
    dp.include_router(startemoji_router)
    dp.include_router(booking_router)
    dp.include_router(salary_router)
    dp.include_router(menu_router)
    dp.include_router(clean_router)

    # 6) Устанавливаем команды
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
        await db.close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())
