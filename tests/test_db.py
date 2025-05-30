import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import db

@pytest.mark.asyncio
async def test_init_db_pool_with_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_create_pool.return_value = AsyncMock()
        await db.init_db_pool()
        assert db.db_pool is not None
        mock_create_pool.assert_awaited_once()

@pytest.mark.asyncio
async def test_init_db_pool_with_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_create_pool.side_effect = Exception("fail")
        with pytest.raises(Exception):
            await db.init_db_pool()

@pytest.mark.asyncio
async def test_close_db_pool_exists():
    mock_pool = AsyncMock()
    db.db_pool = mock_pool
    await db.close_db_pool()
    mock_pool.close.assert_awaited_once()
    assert db.db_pool is None

@pytest.mark.asyncio
async def test_close_db_pool_none():
    db.db_pool = None
    await db.close_db_pool()
    assert db.db_pool is None

@pytest.mark.asyncio
async def test_create_tables_executes_all(monkeypatch):
    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()
    fake_conn.__aenter__.return_value = fake_conn
    class FakePool:
        def acquire(self):
            return fake_conn
    db.db_pool = FakePool()
    await db.create_tables()
    assert fake_conn.execute.await_count >= 6  # Кол-во CREATE TABLE IF NOT EXISTS

@pytest.mark.asyncio
async def test_create_tables_with_exception(monkeypatch):
    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock(side_effect=Exception("fail"))
    fake_conn.__aenter__.return_value = fake_conn
    class FakePool:
        def acquire(self):
            return fake_conn
    db.db_pool = FakePool()
    with pytest.raises(Exception):
        await db.create_tables()
