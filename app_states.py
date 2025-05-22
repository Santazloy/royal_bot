# app_states.py

from aiogram.fsm.state import State, StatesGroup

class BookUserStates(StatesGroup):
    waiting_for_group = State()
    waiting_for_day   = State()
    waiting_for_time  = State()

class BookPaymentStates(StatesGroup):
    waiting_for_amount = State()