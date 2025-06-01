# handlers/booking/data_manager.py

import logging
from typing import Dict, Any
from utils.time_utils import get_adjacent_time_slots
import db
from handlers.startemoji import get_next_emoji

logger = logging.getLogger(__name__)

class BookingDataManager:
    """
    Менеджер локальной in-memory структуры groups_data:
      - booked_slots
      - slot_bookers
      - time_slot_statuses
      - unavailable_slots
    """
    def __init__(self, groups: Dict[str, Any]):
        # храним прямую ссылку на константу constants.booking_const.groups_data
        self.groups = groups

    def list_group_keys(self):
        return list(self.groups.keys())

    def get_group_info(self, group_key: str) -> Dict[str, Any]:
        return self.groups[group_key]

    def book_slot(self, group_key: str, day: str, slot: str, user_id: int, emoji_for_slot: str = None):
        g = self.groups[group_key]
        # 1) отмечаем сам слот
        g["booked_slots"].setdefault(day, []).append(slot)
        g["slot_bookers"][(day, slot)] = user_id
        g["time_slot_statuses"][(day, slot)] = "booked"
        # для отладки или если надо видеть emoji в памяти:
        if emoji_for_slot:
            g.setdefault("slot_emojis", {})[(day, slot)] = emoji_for_slot
        # 2) блокируем соседние
        for adj in get_adjacent_time_slots(slot):
            if adj not in g["booked_slots"].get(day, []):
                g["unavailable_slots"].setdefault(day, set()).add(adj)
                g["time_slot_statuses"][(day, adj)] = "unavailable"
                g["slot_bookers"][(day, adj)] = user_id

# --- Асинхронная функция для бронирования слота с записью в БД и ротацией эмодзи ---
async def async_book_slot(group_key: str, day: str, slot: str, user_id: int):
    """
    Асинхронное бронирование: делает ротацию эмодзи, записывает бронирование в БД и обновляет in-memory.
    """
    emoji_for_slot = await get_next_emoji(user_id)

    # 1. Записываем в БД
    if db.db_pool:
        async with db.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bookings
                    (group_key, day, time_slot, user_id, status, emoji)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (group_key, day, time_slot, user_id)
                DO UPDATE SET status=$5, emoji=$6
                """,
                group_key, day, slot, user_id, "booked", emoji_for_slot
            )

    # 2. Обновляем in-memory
    from constants.booking_const import groups_data
    mgr = BookingDataManager(groups_data)
    mgr.book_slot(group_key, day, slot, user_id, emoji_for_slot=emoji_for_slot)

    logger.info(f"Booked slot: {group_key} {day} {slot} for user {user_id} with emoji {emoji_for_slot}")
    return emoji_for_slot
