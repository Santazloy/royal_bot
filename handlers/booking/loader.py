# handlers/booking/loader.py

from db_access.booking_repo import BookingRepo
from constants.booking_const import groups_data

# инициализируем один раз, при импорте
_repo = BookingRepo()

async def load_slots_from_db() -> None:
    """
    Загружает из БД все брони и статусы и заполняет groups_data.
    main.py по-прежнему вызывает именно эту функцию.
    """
    await _repo.load_data(groups_data)
