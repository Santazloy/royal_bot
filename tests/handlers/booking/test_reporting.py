# tests/handlers/booking/test_reporting.py
import pytest
import inspect
from handlers.booking import reporting
from handlers.booking.reporting import (
    send_booking_report,
    update_group_message,
    send_financial_report,
    safe_delete_and_answer,
)

@pytest.mark.parametrize("func", [
    send_booking_report,
    update_group_message,
    send_financial_report,
    safe_delete_and_answer,
])
def test_reporting_coroutines(func):
    """
    Все функции отчётов и утилит reporting должны быть корутинами
    """
    assert inspect.iscoroutinefunction(func), f"{func.__name__} должна быть корутиной"
