# db_access/booking.py
import logging
from typing import Dict, Any, List
import db
from utils.time_utils import get_adjacent_time_slots

logger = logging.getLogger(__name__)

class BookingRepo:
    """
    Репозиторий, отвечающий и за загрузку из БД в память,
    и за запись новых броней/статусов.
    """

    def __init__(self, pool=None):
        # Можно передать пул явно, иначе берём из db.db_pool
        self.pool = pool

    async def load_data(self, groups_data: Dict[str, Any]) -> None:
        """
        Загружает из БД все брони и статусы и заполняет groups_data.
        """
        pool = self.pool or db.db_pool
        if not pool:
            logger.error("db_pool is None при load_data")
            return

        # 1) Очищаем память
        for g in groups_data.values():
            g["booked_slots"] = {"Сегодня": [], "Завтра": []}
            g["slot_bookers"] = {}
            g["unavailable_slots"] = {"Сегодня": set(), "Завтра": set()}
            g["time_slot_statuses"] = {}

        # 2) Загружаем брони
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT group_key, day, time_slot, user_id FROM bookings"
                )
        except Exception as e:
            logger.error("Ошибка при загрузке bookings: %s", e)
        else:
            for row in rows:
                gk, day, slot, uid = (
                    row["group_key"], row["day"], row["time_slot"], row["user_id"]
                )
                if gk in groups_data and day in groups_data[gk]["booked_slots"]:
                    groups_data[gk]["booked_slots"][day].append(slot)
                    groups_data[gk]["slot_bookers"][(day, slot)] = uid

        # 3) Загружаем статусы
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT group_key, day, time_slot, status, user_id "
                    "FROM group_time_slot_statuses"
                )
        except Exception as e:
            logger.error("Ошибка при загрузке statuses: %s", e)
        else:
            for row in rows:
                gk, day, slot, status, uid = (
                    row["group_key"], row["day"], row["time_slot"],
                    row["status"], row["user_id"]
                )
                if gk in groups_data:
                    groups_data[gk]["time_slot_statuses"][(day, slot)] = status
                    if status == "unavailable":
                        groups_data[gk]["unavailable_slots"][day].add(slot)

    async def add_booking(
        self,
        group_key: str,
        day: str,
        time_slot: str,
        user_id: int,
        start_time: str
    ) -> None:
        """
        Добавляет новую бронь и сразу помечает её в обоих таблицах.
        """
        pool = self.pool or db.db_pool
        if not pool:
            logger.error("db_pool is None при add_booking")
            return

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bookings (group_key, day, time_slot, user_id, status, start_time)
                VALUES ($1, $2, $3, $4, 'booked', $5)
                """,
                group_key, day, time_slot, user_id, start_time
            )
            await conn.execute(
                """
                INSERT INTO group_time_slot_statuses
                    (group_key, day, time_slot, status, user_id)
                VALUES ($1, $2, $3, 'booked', $4)
                ON CONFLICT (group_key, day, time_slot)
                DO UPDATE SET status = excluded.status, user_id = excluded.user_id
                """,
                group_key, day, time_slot, user_id
            )

    async def mark_unavailable(
        self,
        group_key: str,
        day: str,
        slot: str,
        user_id: int
    ) -> None:
        """
        Помечает конкретный слот как 'unavailable'.
        """
        pool = self.pool or db.db_pool
        if not pool:
            logger.error("db_pool is None при mark_unavailable")
            return

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO group_time_slot_statuses
                    (group_key, day, time_slot, status, user_id)
                VALUES ($1, $2, $3, 'unavailable', $4)
                ON CONFLICT (group_key, day, time_slot)
                DO UPDATE SET status = excluded.status, user_id = excluded.user_id
                """,
                group_key, day, slot, user_id
            )

class BookingDataManager:
    """
    Менеджер, который работает с тем же словарём groups_data
    и добавляет логику соседних слотов.
    """
    def __init__(self, groups_data: Dict[str, Any]):
        self.groups = groups_data

    def list_group_keys(self) -> List[str]:
        return list(self.groups.keys())

    def get_group_info(self, group_key: str) -> Dict[str, Any]:
        return self.groups[group_key]

    def book_slot(self, group_key: str, day: str, slot: str, user_id: int):
        """
        Помечает слот забронированным и блокирует соседние.
        """
        g = self.groups[group_key]
        g["booked_slots"][day].append(slot)
        g["slot_bookers"][(day, slot)] = user_id
        g["time_slot_statuses"][(day, slot)] = "booked"

        for adj in get_adjacent_time_slots(slot):
            if adj not in g["booked_slots"][day]:
                g["unavailable_slots"][day].add(adj)
                g["time_slot_statuses"][(day, adj)] = "unavailable"
                g["slot_bookers"][(day, adj)] = user_id
