# db.py

import os
import logging
import ssl
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
        conn_str = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
        logging.info("Подключаемся к БД: %s", conn_str)

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    db_pool = await asyncpg.create_pool(dsn=conn_str, ssl=ssl_ctx)
    logging.info("Подключение к PostgreSQL установлено.")


async def create_tables():
    if db_pool is None:
        raise RuntimeError("db_pool is None! Сначала вызовите init_db_pool().")

    async with db_pool.acquire() as conn:
        # --- bookings ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
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
                id BIGSERIAL,
                PRIMARY KEY (group_key, day, time_slot, user_id)
            );
            """
        )
        await conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                      FROM pg_constraint
                     WHERE conname = 'bookings_pkey'
                       AND conrelid = 'bookings'::regclass
                ) THEN
                    ALTER TABLE bookings
                    ADD PRIMARY KEY (group_key, day, time_slot, user_id);
                END IF;
            END;
            $$;
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
        await conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                      FROM pg_constraint
                     WHERE conname = 'group_time_slot_statuses_pkey'
                       AND conrelid = 'group_time_slot_statuses'::regclass
                ) THEN
                    ALTER TABLE group_time_slot_statuses
                    ADD PRIMARY KEY (group_key, day, time_slot);
                END IF;
            END;
            $$;
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
                language TEXT,
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
                next_idx BIGINT DEFAULT 0,
                emojis TEXT DEFAULT ''
            );
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

        # --- gpt_memory ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gpt_memory (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                user_name TEXT,
                message_type TEXT,
                content TEXT,
                timestamp BIGINT
            );
            """
        )

        # --- embeddings ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                id SERIAL PRIMARY KEY,
                group_id BIGINT,
                user_id BIGINT,
                embedding_vector FLOAT8[],
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        # --- messages ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                group_id BIGINT,
                user_id BIGINT,
                user_name TEXT,
                text TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        # --- message_history ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_history (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                user_id BIGINT,
                role TEXT,
                content TEXT
            );
            """
        )

        # --- news ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news (
                id SERIAL PRIMARY KEY,
                file_ids TEXT,
                text TEXT
            );
            """
        )

        # --- reminders ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                booking_id BIGINT,
                type TEXT
            );
            """
        )

        # --- mathematic_groups ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mathematic_groups (
                group_id BIGINT PRIMARY KEY,
                name TEXT,
                total FLOAT
            );
            """
        )

        # --- individual_groups ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS individual_groups (
                id SERIAL PRIMARY KEY,
                group_id BIGINT,
                name TEXT,
                user_totals TEXT
            );
            """
        )

        # --- group_photos ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS group_photos (
                id SERIAL PRIMARY KEY,
                group_key TEXT,
                file_ids TEXT,
                description TEXT
            );
            """
        )

        # --- distributions ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS distributions (
                id SERIAL PRIMARY KEY,
                group_key TEXT,
                status_code TEXT,
                amount BIGINT,
                distribution_amount BIGINT,
                date TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        # --- transactions ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                user_id BIGINT,
                amount NUMERIC,
                type VARCHAR,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        # --- balances ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS balances (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                balance NUMERIC,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        # --- stats ---
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stats (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                report_date DATE,
                period_type VARCHAR,
                plus_total NUMERIC,
                minus_total NUMERIC,
                net_result NUMERIC,
                balance_start NUMERIC,
                balance_end NUMERIC,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        logging.info("Все таблицы созданы или проверены.")


async def close_db_pool():
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None
        logging.info("Пул соединений закрыт.")
