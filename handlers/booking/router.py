# handlers/booking/router.py

import logging
from aiogram import Router
import db
from db_access.booking_repo import BookingRepo
from handlers.booking.data_manager import BookingDataManager
from constants.booking_const import groups_data

logger = logging.getLogger(__name__)

# Создаём один «сборный» роутер для всего модуля бронирования:
router = Router()

# Инициализируем репозиторий и менеджер данных (для FSM):
repo = BookingRepo(db.db_pool)
data_mgr = BookingDataManager(groups_data)

# Импортируем вложенные «частичные» роутеры:
from handlers.booking.user_flow import router as user_flow_router
from handlers.booking.admin_flow import router as admin_flow_router
from handlers.booking.payment_flow import router as payment_flow_router
from handlers.booking.reporting import router as reporting_router
from handlers.booking.cancelbook import router as cancelbook_router

# Подключаем их **внутрь** общего booking-роутера:
router.include_router(user_flow_router)
router.include_router(admin_flow_router)
router.include_router(payment_flow_router)
router.include_router(reporting_router)
router.include_router(cancelbook_router)
