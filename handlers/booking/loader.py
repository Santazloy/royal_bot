# handlers/booking/loader.py

import logging
import db
from constants.booking_const import groups_data

logger = logging.getLogger(__name__)

async def load_slots_from_db():
    """
    Загружает из БД все брони и статусы и заполняет groups_data:
      - booked_slots и slot_bookers из таблицы bookings
      - time_slot_statuses из таблицы group_time_slot_statuses
      - unavailable_slots можно оставить пустыми (если нужна персистентная логика, можно аналогично хранить в БД)
    """
    pool = db.db_pool
    # 1) Load bookings
    try:
        async with pool.acquire() as con:
            rows = await con.fetch(
                "SELECT group_key, day, time_slot, user_id FROM bookings"
            )
    except Exception as e:
        logger.error("Ошибка при загрузке bookings: %s", e)
        return

    # очищаем старые
    for g in groups_data.values():
        g["booked_slots"] = {"Сегодня": [], "Завтра": []}
        g["slot_bookers"] = {}

    for row in rows:
        gk, day, slot, uid = row["group_key"], row["day"], row["time_slot"], row["user_id"]
        if gk in groups_data and day in groups_data[gk]["booked_slots"]:
            groups_data[gk]["booked_slots"][day].append(slot)
            groups_data[gk]["slot_bookers"][(day, slot)] = uid

    # 2) Load statuses
    try:
        async with pool.acquire() as con:
            rows = await con.fetch(
                "SELECT group_key, day, time_slot, status FROM group_time_slot_statuses"
            )
    except Exception as e:
        logger.error("Ошибка при загрузке group_time_slot_statuses: %s", e)
        return

    # очищаем старые
    for g in groups_data.values():
        g["time_slot_statuses"] = {}

    for row in rows:
        gk, day, slot, status = (
            row["group_key"], row["day"], row["time_slot"], row["status"]
        )
        if gk in groups_data:
            groups_data[gk]["time_slot_statuses"][(day, slot)] = status
