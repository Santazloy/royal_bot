# tests/handlers/booking/test_user_flow.py
import pytest
import inspect
from handlers.booking import user_flow
from handlers.booking.user_flow import (
    cmd_book,
    user_select_group,
    user_select_day,
    user_select_time,
)

@pytest.mark.parametrize("func", [
    cmd_book,
    user_select_group,
    user_select_day,
    user_select_time,
])
def test_user_flow_coroutines(func):
    """
    Все ключевые хендлеры user_flow должны быть корутинами
    """
    assert inspect.iscoroutinefunction(func), f"{func.__name__} должна быть корутиной"
