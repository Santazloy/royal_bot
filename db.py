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
        PGHOST = os.getenv("PGHOST", "")
        PGPORT = os.getenv("PGPORT", "5432")
        PGUSER = os.getenv("PGUSER", "")
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
    if db_pool is None:
        raise RuntimeError("db_pool is None! Сначала вызовите init_db_pool().")

    async with db_pool.acquire() as conn:
        # --- bookings ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id BIGSERIAL UNIQUE,
                group_key TEXT NOT NULL,
                day TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                user_id BIGINT NOT NULL,
                status TEXT NOT NULL,
                status_code TEXT,
                start_time TIMESTAMPTZ,
                payment_method TEXT,
                amount INTEGER,
                emoji TEXT DEFAULT '',
                PRIMARY KEY (group_key, day, time_slot, user_id)
            );
            """
        )

        # --- group_time_slot_statuses ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS group_time_slot_statuses (
                group_key TEXT NOT NULL,
                day TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT NOT NULL,
                user_id BIGINT,
                PRIMARY KEY (group_key, day, time_slot)
            );
            """
        )

        # --- group_financial_data ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS group_financial_data (
                group_key TEXT PRIMARY KEY,
                salary_option INTEGER NOT NULL DEFAULT 1,
                salary BIGINT NOT NULL DEFAULT 0,
                cash BIGINT NOT NULL DEFAULT 0,
                message_id BIGINT
            );
            """
        )

        # --- users ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance BIGINT NOT NULL DEFAULT 0,
                profit BIGINT NOT NULL DEFAULT 0,
                monthly_profit BIGINT NOT NULL DEFAULT 0
            );
            """
        )

        # --- user_emojis ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_emojis (
                user_id BIGINT PRIMARY KEY,
                emojis TEXT DEFAULT ''
            );
            """
        )

        # переименование старого столбца emoji -> emojis
        await conn.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                      FROM information_schema.columns
                     WHERE table_schema = 'public'
                       AND table_name   = 'user_emojis'
                       AND column_name  = 'emoji'
                ) THEN
                    EXECUTE 'ALTER TABLE user_emojis RENAME COLUMN emoji TO emojis';
                END IF;
            END;
            $$;
            """
        )

        # --- user_settings ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id BIGINT PRIMARY KEY,
                language TEXT NOT NULL
            );
            """
        )

        # --- гарантируем наличие id в bookings ---
        await conn.execute(
            """
            ALTER TABLE bookings
            ADD COLUMN IF NOT EXISTS id BIGSERIAL UNIQUE;
            """
        )
        await conn.execute(
            """
            UPDATE bookings
               SET id = nextval(pg_get_serial_sequence('bookings','id'))
             WHERE id IS NULL;
            """
        )

        logging.info("Все таблицы созданы или проверены.")


async def close_db_pool():
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None
        logging.info("Пул соединений закрыт.")
