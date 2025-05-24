# handlers/booking/router.py
import logging
from aiogram import Router
import db
from db_access.booking_repo import BookingRepo
from handlers.booking.data_manager import BookingDataManager
from constants.booking_const import groups_data

logger = logging.getLogger(__name__)

router = Router()
repo = BookingRepo(db.db_pool)
data_mgr = BookingDataManager(groups_data)

# Импортируем модули-обработчики — их декораторы привяжутся к этому же `router`
from handlers.booking import user_flow, admin_flow, payment_flow, reporting, rewards, cancelbook
