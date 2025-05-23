# tests/handlers/booking/test_router.py
import pytest
import inspect
from aiogram import Router as AiogramRouter
from handlers.booking.router import router

def test_router_instance():
    """
    Проверяем, что объект router — это экземпляр aiogram.Router
    """
    assert isinstance(router, AiogramRouter), "router должен быть экземпляром aiogram.Router"
