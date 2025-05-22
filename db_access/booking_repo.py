import logging
from typing import Dict, Any
import db
from utils.time_utils import get_adjacent_time_slots

logger = logging.getLogger(__name__)

class BookingRepo:
    def __init__(self, pool):
        self.pool = pool

    async def load_data(self, groups_data: Dict[str, Any]) -> None:
        """
        Очищает и загружает из БД:
          - booked_slots, slot_bookers
          - time_slot_statuses, unavailable_slots
        """
        pool = db.db_pool or self.pool
        # 1) bookings
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT group_key, day, time_slot, user_id FROM bookings"
                )
        except Exception as e:
            logger.error("Ошибка load_data/bookings: %s", e)
            return

        # Reset all
        for g in groups_data.values():
            g["booked_slots"] = {"Сегодня": [], "Завтра": []}
            g["slot_bookers"] = {}
            g["unavailable_slots"] = {"Сегодня": set(), "Завтра": set()}
            g["time_slot_statuses"] = {}

        # Fill bookings
        for row in rows:
            gk, day, slot, uid = row["group_key"], row["day"], row["time_slot"], row["user_id"]
            if gk in groups_data and day in groups_data[gk]["booked_slots"]:
                groups_data[gk]["booked_slots"][day].append(slot)
                groups_data[gk]["slot_bookers"][(day, slot)] = uid
                groups_data[gk]["time_slot_statuses"][(day, slot)] = "booked"

        # 2) statuses
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT group_key, day, time_slot, status, user_id FROM group_time_slot_statuses"
                )
        except Exception as e:
            logger.error("Ошибка load_data/statuses: %s", e)
            return

        for row in rows:
            gk, day, slot, st, uid = (
                row["group_key"], row["day"], row["time_slot"], row["status"], row["user_id"]
            )
            if gk in groups_data:
                groups_data[gk]["time_slot_statuses"][(day, slot)] = st
                if st == "unavailable":
                    groups_data[gk]["unavailable_slots"][day].add(slot)

    async def add_booking(
        self,
        group_key: str,
        day: str,
        time_slot: str,
        user_id: int,
        start_time: str
    ) -> None:
        pool = db.db_pool or self.pool
        async with pool.acquire() as conn:
            # основной booking
            await conn.execute(
                """
                INSERT INTO bookings
                  (group_key, day, time_slot, user_id, status, start_time)
                VALUES ($1,$2,$3,$4,'booked',$5)
                """, group_key, day, time_slot, user_id, start_time
            )
            # статус в отдельной таблице
            await conn.execute(
                """
                INSERT INTO group_time_slot_statuses
                  (group_key, day, time_slot, status, user_id)
                VALUES ($1,$2,$3,'booked',$4)
                ON CONFLICT (group_key,day,time_slot)
                  DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                """, group_key, day, time_slot, user_id
            )

    async def mark_unavailable(
        self,
        group_key: str,
        day: str,
        slot: str,
        user_id: int
    ) -> None:
        pool = db.db_pool or self.pool
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO group_time_slot_statuses
                  (group_key, day, time_slot, status, user_id)
                VALUES ($1,$2,$3,'unavailable',$4)
                ON CONFLICT (group_key,day,time_slot)
                  DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                """, group_key, day, slot, user_id
            )
