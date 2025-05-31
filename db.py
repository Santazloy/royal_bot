# db.py

import os
import logging
import asyncpg

db_pool: asyncpg.pool.Pool | None = None

async def init_db_pool():
    global db_pool
    conn_str = os.getenv("DATABASE_URL", "")
    if conn_str:
        logging.info("Подключаемся к БД: %s", conn_str)
    else:
        PGHOST     = os.getenv("PGHOST", "")
        PGPORT     = os.getenv("PGPORT", "5432")
        PGUSER     = os.getenv("PGUSER", "")
        PGPASSWORD = os.getenv("PGPASSWORD", "")
        PGDATABASE = os.getenv("PGDATABASE", "")
        conn_str = (
            f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
            "?sslmode=require"
        )
        logging.info("Подключаемся к БД: %s", conn_str)

    db_pool = await asyncpg.create_pool(dsn=conn_str)
    logging.info("Подключение к PostgreSQL установлено.")

async def create_tables():
    if not db_pool:
        raise RuntimeError("db_pool is None! Сначала вызовите init_db_pool().")

    async with db_pool.acquire() as conn:
        # ---  bookings  ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id BIGSERIAL UNIQUE,                         -- ★ добавлено
                group_key TEXT NOT NULL,
                day TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                user_id BIGINT NOT NULL,
                status TEXT NOT NULL,
                status_code TEXT,
                start_time TIMESTAMPTZ,
                payment_method TEXT,
                amount INTEGER,
                PRIMARY KEY (group_key, day, time_slot, user_id)
            );
        """)
        # 🔻 оставшиеся CREATE TABLE ... без изменений 🔻
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS group_time_slot_statuses (
                group_key TEXT NOT NULL,
                day TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT NOT NULL,
                user_id BIGINT,
                PRIMARY KEY (group_key, day, time_slot)
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS group_financial_data (
                group_key TEXT PRIMARY KEY,
                salary_option INTEGER NOT NULL DEFAULT 1,
                salary BIGINT   NOT NULL DEFAULT 0,
                cash   BIGINT   NOT NULL DEFAULT 0,
                message_id BIGINT
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance BIGINT   NOT NULL DEFAULT 0,
                profit  BIGINT   NOT NULL DEFAULT 0,
                monthly_profit BIGINT NOT NULL DEFAULT 0
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_emojis (
                user_id BIGINT PRIMARY KEY,
                emoji TEXT DEFAULT ''
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id BIGINT PRIMARY KEY,
                language TEXT NOT NULL
            );
        """)
        # --- гарантируем наличие id, если таблица была создана раньше ---
        await conn.execute("""
            ALTER TABLE bookings
            ADD COLUMN IF NOT EXISTS id BIGSERIAL UNIQUE;
        """)
        await conn.execute("""
            UPDATE bookings
            SET    id = nextval(pg_get_serial_sequence('bookings','id'))
            WHERE  id IS NULL;
        """)
        logging.info("Все таблицы созданы или проверены.")

async def close_db_pool():
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None
        logging.info("Пул соединений закрыт.")
