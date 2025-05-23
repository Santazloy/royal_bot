# tests/handlers/booking/test_loader.py

import pytest
from unittest.mock import AsyncMock, patch
from handlers.booking.loader import load_slots_from_db
from constants.booking_const import groups_data


@pytest.mark.asyncio
async def test_load_slots_from_db_success():
    fake_conn = AsyncMock()
    fake_conn.fetch.side_effect = [
        [  # bookings
            {"group_key": "Royal_1", "day": "Сегодня", "time_slot": "10:00", "user_id": 1}
        ],
        [  # statuses
            {"group_key": "Royal_1", "day": "Сегодня", "time_slot": "10:00", "status": "unavailable"}
        ]
    ]
    fake_conn.__aenter__.return_value = fake_conn

    with patch("db.db_pool", new=type("Pool", (), {"acquire": lambda self: fake_conn})()):
        await load_slots_from_db()

    assert "10:00" in groups_data["Royal_1"]["booked_slots"]["Сегодня"]
    assert groups_data["Royal_1"]["slot_bookers"][("Сегодня", "10:00")] == 1
    assert groups_data["Royal_1"]["time_slot_statuses"][("Сегодня", "10:00")] == "unavailable"
    assert "10:00" in groups_data["Royal_1"]["unavailable_slots"]["Сегодня"]


@pytest.mark.asyncio
async def test_load_slots_from_db_no_pool():
    with patch("db.db_pool", new=None):
        await load_slots_from_db()  # should not raise anything
