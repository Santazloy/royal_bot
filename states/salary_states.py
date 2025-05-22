from aiogram.fsm.state import State, StatesGroup

class SalaryStates(StatesGroup):
    waiting_for_group_choice = State()
    waiting_for_option_choice = State()
