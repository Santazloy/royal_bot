# handlers/booking/loader.py

import logging
import db
from constants.booking_const import groups_data

logger = logging.getLogger(__name__)

async def load_slots_from_db():
    """
    Загружает из БД все брони и статусы и заполняет groups_data:
      - booked_slots и slot_bookers и slot_emojis из таблицы bookings
      - time_slot_statuses из таблицы group_time_slot_statuses
      - unavailable_slots для статусов 'unavailable'
    """
    pool = db.db_pool
    if not pool:
        logger.error("db_pool is None при загрузке слотов")
        return

    # 1) Очищаем память
    for g in groups_data.values():
        g["booked_slots"] = {"Сегодня": [], "Завтра": []}
        g["slot_bookers"] = {}
        g["time_slot_statuses"] = {}
        g["unavailable_slots"] = {"Сегодня": set(), "Завтра": set()}
        g["slot_emojis"] = {}

    # 2) Загружаем bookings c emoji
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT group_key, day, time_slot, user_id, emoji FROM bookings"
        )
    for row in rows:
        gk, day, slot, uid, emoji = row["group_key"], row["day"], row["time_slot"], row["user_id"], row["emoji"]
        if gk in groups_data and day in groups_data[gk]["booked_slots"]:
            groups_data[gk]["booked_slots"][day].append(slot)
            groups_data[gk]["slot_bookers"][(day, slot)] = uid
            groups_data[gk]["slot_emojis"][(day, slot)] = emoji or "❓"

    # 3) Загружаем статусы
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT group_key, day, time_slot, status FROM group_time_slot_statuses"
        )
    for row in rows:
        gk, day, slot, st = (
            row["group_key"], row["day"], row["time_slot"], row["status"]
        )
        if gk in groups_data:
            groups_data[gk]["time_slot_statuses"][(day, slot)] = st
            if st == "unavailable":
                groups_data[gk]["unavailable_slots"][day].add(slot)
