# db_access/booking_repo.py

from asyncpg import Pool

class BookingRepo:
    def __init__(self, db_pool: Pool):
        self.pool = db_pool

    async def add_booking(self, group_key: str, day: str, time_slot: str, user_id: int, start_time: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO bookings (group_key, day, time_slot, user_id, status, start_time)
                VALUES ($1,$2,$3,$4,'booked',$5)
                """,
                group_key, day, time_slot, user_id, start_time
            )
            await conn.execute(
                """
                INSERT INTO group_time_slot_statuses (group_key, day, time_slot, status, user_id)
                VALUES ($1,$2,$3,'booked',$4)
                ON CONFLICT (group_key, day, time_slot)
                DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                """,
                group_key, day, time_slot, user_id
            )

    async def mark_unavailable(self, group_key: str, day: str, slot: str, user_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO group_time_slot_statuses (group_key, day, time_slot, status, user_id)
                VALUES ($1,$2,$3,'unavailable',$4)
                ON CONFLICT (group_key, day, time_slot)
                DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                """,
                group_key, day, slot, user_id
            )