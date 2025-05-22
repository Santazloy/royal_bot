import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import TELEGRAM_BOT_TOKEN
import db
from constants.booking_const import groups_data
from db_access.booking_repo import BookingRepo
from handlers.booking.router import router as booking_router, update_group_message
# … остальные routers …
from handlers.salary import salary_router, load_salary_data_from_db
from handlers.clean import router as clean_router

async def main():
    logging.basicConfig(level=logging.INFO)
    # 1) пул
    await db.init_db_pool()
    # 2) таблицы
    await db.create_tables()

    # 3) загрузить слоты/статусы
    repo = BookingRepo(db.db_pool)
    await repo.load_data(groups_data)
    logging.info("Слоты загружены из БД")

    # 4) бот + диспетчер
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    # 5) обновить/создать меню в группах
    for gk in groups_data:
        await update_group_message(bot, gk)

    # 6) /salary state
    await load_salary_data_from_db()

    # 7) include routers
    dp.include_router(booking_router)
    dp.include_router(salary_router)
    dp.include_router(clean_router)
    # … остальные …

    # 8) set commands
    await bot.set_my_commands([
        BotCommand(command="/book",   description="Забронировать слот"),
        BotCommand(command="/salary", description="Настройки salary (админ)"),
        # …
    ])

    # 9) polling
    try:
        await dp.start_polling(bot)
    finally:
        await db.close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())
