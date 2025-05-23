# tests/test_main.py

import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_main_run():
    with patch("main.db.init_db_pool", new=AsyncMock()), \
         patch("main.db.create_tables", new=AsyncMock()), \
         patch("main.BookingRepo.load_data", new=AsyncMock()), \
         patch("main.load_salary_data_from_db", new=AsyncMock()), \
         patch("main.Bot.set_my_commands", new=AsyncMock()), \
         patch("main.Dispatcher.start_polling", new=AsyncMock()), \
         patch("main.db.close_db_pool", new=AsyncMock()):
        from main import main
        await main()
