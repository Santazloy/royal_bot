# states/admin_states.py
from aiogram.fsm.state import StatesGroup, State

class AdminStates(StatesGroup):
    menu = State()
