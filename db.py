# db.py
import os
import logging
import asyncpg

db_pool = None

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
        conn_str = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}?sslmode=require"
        logging.info("Подключаемся к БД: %s", conn_str)

    db_pool = await asyncpg.create_pool(dsn=conn_str)
    logging.info("Подключение к PostgreSQL установлено.")

async def create_tables():
    if not db_pool:
        raise RuntimeError("db_pool is None! Сначала вызовите init_db_pool().")

    async with db_pool.acquire() as conn:
        # Создаём таблицу news
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id BIGSERIAL PRIMARY KEY,
                file_ids TEXT,
                text TEXT
            )
        """)

        # Создаём таблицу user_emojis
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_emojis (
                user_id BIGINT PRIMARY KEY,
                emoji TEXT DEFAULT ''
            )
        """)

        logging.info("Таблицы news и user_emojis созданы/проверены.")

async def close_db_pool():
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None
        logging.info("Пул соединений закрыт.")