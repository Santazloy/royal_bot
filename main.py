# main.py

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_BOT_TOKEN
import db

# Импортируем «сборные» роутеры
from handlers.group_id import router as group_id_router
from handlers.idphoto import router as idphoto_router
from handlers.startemoji import router as startemoji_router
from handlers.booking.router import router as booking_router     # <<< единственный вызов всех booking-хендлеров
from handlers.salary import salary_router, load_salary_data_from_db
from handlers.menu import menu_router
from handlers.clean import router as clean_router
from handlers.language import language_router
from handlers.money import money_router
from handlers.menu_ad import menu_ad_router
from handlers.users import users_router
from handlers.leonard import leonard_menu_router
from handlers.file import router as file_router
# from handlers.gpt import router as gpt_router, on_startup as gpt_on_startup
from handlers.ai import router as ai_router
from handlers.rules import router as rules_router
from handlers.exchange import router as exchange_router
from handlers.next import router as next_router, register_daily_scheduler
from handlers.andry import router as andry_router
from db_access.booking_repo import BookingRepo

async def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    logger = logging.getLogger(__name__)

    logger.info("Запуск приложения...")

    # 1) Инициализация базы данных
    logger.debug("Инициализация подключения к базе данных...")
    await db.init_db_pool()
    await db.create_tables()
    logger.info("База данных и таблицы успешно инициализированы.")

    # 2) Загрузка данных бронирований в память
    logger.debug("Загрузка данных бронирований...")
    repo = BookingRepo(db.db_pool)
    await repo.load_data()
    logger.info("Слоты и статусы успешно загружены из БД.")

    # 3) Загрузка настроек salary
    logger.debug("Загрузка настроек salary из БД...")
    await load_salary_data_from_db()
    logger.info("Настройки salary успешно загружены из БД.")

    # 4) Создание Bot и Dispatcher
    logger.debug("Создание экземпляра бота и диспетчера...")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # 5) Регистрируем on_startup-хендлер GPT (если нужен)
    # dp.startup.register(gpt_on_startup)

    # 6) Подключаем роутеры в нужном порядке:
    logger.debug("Подключение роутеров...")

    # ─────── сначала «точечные» роутеры, которые не ловят свободный текст:
    dp.include_router(language_router)
    dp.include_router(next_router)
    dp.include_router(group_id_router)
    dp.include_router(idphoto_router)
    dp.include_router(startemoji_router)

    # ─────── затем **booking_router** (FSM-flow бронирования):
    dp.include_router(booking_router)
    dp.include_router(andry_router)
    # ─────── дальше идут остальные «общие» роутеры:
    dp.include_router(salary_router)
    dp.include_router(leonard_menu_router)
    dp.include_router(rules_router)
    dp.include_router(exchange_router)
    dp.include_router(clean_router)
    dp.include_router(ai_router)
    dp.include_router(money_router)
    dp.include_router(users_router)
    dp.include_router(menu_ad_router)
    dp.include_router(menu_router)
    dp.include_router(file_router)
    # dp.include_router(gpt_router)  # если нужен роутер GPT
    logger.info("Все роутеры успешно подключены.")

    # 7) Регистрируем планировщик (из handlers/next.py)
    register_daily_scheduler(dp, bot)

    # 8) Устанавливаем список команд бота (меню команд):
    logger.debug("Установка команд бота...")
    commands = [
        BotCommand(command="/start", description="Начать"),
        BotCommand(command="/help", description="Помощь"),
        BotCommand(command="/news", description="Показать новости"),
        BotCommand(command="/id", description="Получить file_id фото"),
        BotCommand(command="/emoji", description="Смена эмоджи (только для админа)"),
        BotCommand(command="/book", description="Забронировать слот"),
        BotCommand(command="/salary", description="Настроить salary (админ)"),
        BotCommand(command="/money", description="Изменить зарплату/наличные"),
        BotCommand(command="/off", description="Отменить свою бронь"),
        BotCommand(command="/offad", description="Отмена чужих бронирований (админ)"),
        BotCommand(command="/ad", description="Открыть админ-меню"),
        BotCommand(command="/users", description="Управление пользователями"),
        BotCommand(command="/gpt_init", description="Инициализировать таблицу памяти GPT"),
        BotCommand(command="/generate", description="Сгенерировать изображение по запросу"),
        # Пример добавления команды Tarot (если вы добавляли handlers/taro_module.py):
        BotCommand(command="/tarot", description="Вытянуть 3 карты Таро Манара")
    ]
    await bot.set_my_commands(commands)
    logger.info("Команды бота успешно установлены.")

    # 9) Удаляем webhook (если был) и запускаем polling
    logger.debug("Удаление webhook (если установлен)...")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook удалён. Ждём 2 секунды...")
    await asyncio.sleep(2)

    logger.info("Запуск polling для получения обновлений от Telegram...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error("Ошибка во время polling: %s", e)
    finally:
        logger.debug("Закрытие подключения к базе данных...")
        await db.close_db_pool()
        logger.info("Подключение к базе данных закрыто. Завершение работы приложения.")


if __name__ == "__main__":
    asyncio.run(main())
