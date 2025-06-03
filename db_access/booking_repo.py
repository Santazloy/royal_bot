# db_access/booking_repo.py

import logging
from typing import Dict, Any, List, Tuple
import db
from constants.booking_const import groups_data
from utils.time_utils import get_adjacent_time_slots

logger = logging.getLogger(__name__)

class BookingRepo:
    def __init__(self, pool):
        self.pool = pool

    async def load_data(self) -> None:
        pool = db.db_pool or self.pool
        if not pool:
            logger.error("db_pool is None при load_data")
            return

        for g in groups_data.values():
            g["booked_slots"]      = {"Сегодня": [], "Завтра": []}
            g["slot_bookers"]      = {}
            g["time_slot_statuses"] = {}
            g["unavailable_slots"] = {"Сегодня": set(), "Завтра": set()}

        async with pool.acquire() as conn:
            bookings = await conn.fetch(
                "SELECT group_key, day, time_slot, user_id FROM bookings"
            )
        for r in bookings:
            gk, day, slot, uid = r["group_key"], r["day"], r["time_slot"], r["user_id"]
            if gk in groups_data and day in groups_data[gk]["booked_slots"]:
                groups_data[gk]["booked_slots"][day].append(slot)
                groups_data[gk]["slot_bookers"][(day, slot)] = uid

        async with pool.acquire() as conn:
            statuses = await conn.fetch(
                "SELECT group_key, day, time_slot, status, user_id "
                "FROM group_time_slot_statuses"
            )
        for r in statuses:
            gk, day, slot, st, uid = r["group_key"], r["day"], r["time_slot"], r["status"], r["user_id"]
            if gk in groups_data:
                groups_data[gk]["time_slot_statuses"][(day, slot)] = st
                if st == "unavailable":
                    groups_data[gk]["unavailable_slots"][day].add(slot)

    async def add_booking(
        self, group_key: str, day: str,
        time_slot: str, user_id: int,
        start_time
    ) -> None:
        pool = db.db_pool or self.pool
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bookings
                  (group_key, day, time_slot, user_id, status, status_code, start_time)
                VALUES ($1,$2,$3,$4,'booked','', $5)
                """,
                group_key, day, time_slot, user_id, start_time
            )
            await conn.execute(
                """
                INSERT INTO group_time_slot_statuses
                  (group_key, day, time_slot, status, user_id)
                VALUES ($1,$2,$3,'booked',$4)
                ON CONFLICT (group_key, day, time_slot)
                DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                """,
                group_key, day, time_slot, user_id
            )

    async def mark_unavailable(
        self, group_key: str, day: str, slot: str, user_id: int
    ) -> None:
        pool = db.db_pool or self.pool
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO group_time_slot_statuses
                  (group_key, day, time_slot, status, user_id)
                VALUES ($1,$2,$3,'unavailable',$4)
                ON CONFLICT (group_key, day, time_slot)
                DO UPDATE SET status='unavailable', user_id=excluded.user_id
                """,
                group_key, day, slot, user_id
            )

    async def cancel_booking(
        self, group_key: str, day: str, slot: str
    ) -> None:
        pool = db.db_pool or self.pool
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
                group_key, day, slot
            )
            await conn.execute(
                "DELETE FROM group_time_slot_statuses "
                "WHERE group_key=$1 AND day=$2 AND time_slot=$3",
                group_key, day, slot
            )

    async def update_status(
        self, group_key: str, day: str,
        slot: str, status_code: str, emoji: str, user_id: int
    ) -> None:
        pool = db.db_pool or self.pool
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE bookings
                SET status_code=$1, status=$2
                WHERE group_key=$3 AND day=$4 AND time_slot=$5
                """,
                status_code, emoji, group_key, day, slot
            )
            await conn.execute(
                """
                INSERT INTO group_time_slot_statuses
                  (group_key, day, time_slot, status, user_id)
                VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (group_key, day, time_slot)
                DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                """,
                group_key, day, slot, emoji, user_id
            )
