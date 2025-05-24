# main.py

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import TELEGRAM_BOT_TOKEN
import db

# роутеры
from handlers.group_id import router as group_id_router
from handlers.news import router as news_router
from handlers.idphoto import router as idphoto_router
from handlers.startemoji import router as startemoji_router
from handlers.booking.router import router as booking_router
from handlers.salary import salary_router, load_salary_data_from_db
from handlers.menu import menu_router
from handlers.clean import router as clean_router
from handlers.language import language_router
from handlers.money import money_router
from handlers.menu_ad import menu_ad_router  # ВАЖНО! Только импорт!

from db_access.booking_repo import BookingRepo

async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init_db_pool()
    await db.create_tables()
    repo = BookingRepo(db.db_pool)
    await repo.load_data()
    logging.info("Слоты и статусы загружены из БД.")
    await load_salary_data_from_db()
    logging.info("Настройки salary загружены из БД.")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(language_router)
    dp.include_router(group_id_router)
    dp.include_router(news_router)
    dp.include_router(idphoto_router)
    dp.include_router(startemoji_router)
    dp.include_router(booking_router)
    dp.include_router(salary_router)
    dp.include_router(clean_router)
    dp.include_router(money_router)
    dp.include_router(menu_ad_router)   # Только так!
    dp.include_router(menu_router)

    await bot.set_my_commands([
        BotCommand(command="/start",  description="Начать"),
        BotCommand(command="/help",   description="Помощь"),
        BotCommand(command="/added",  description="Управление новостями"),
        BotCommand(command="/news",   description="Показать новости"),
        BotCommand(command="/id",     description="Получить file_id фото"),
        BotCommand(command="/emoji",  description="Смена эмоджи (только для админа)"),
        BotCommand(command="/book",   description="Забронировать слот"),
        BotCommand(command="/salary", description="Настроить salary (админ)"),
        BotCommand(command="/money", description="Изменить зарплату/наличные"),
        BotCommand(command="/off", description="Отменить свою бронь"),
        BotCommand(command="/offad", description="Отмена чужих броней (админ)"),
        BotCommand(command="/ad", description="Открыть админ-меню"),
    ])
    try:
        await dp.start_polling(bot)
    finally:
        await db.close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())
