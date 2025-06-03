# handlers/states.py

from aiogram.fsm.state import StatesGroup, State

# --- Бронирование пользователя ---
class BookUserStates(StatesGroup):
    waiting_for_group = State()
    waiting_for_day   = State()
    waiting_for_time  = State()

# --- Платеж (бронирование) ---
class BookPaymentStates(StatesGroup):
    waiting_for_amount = State()

# --- Настройки зарплаты (salary) ---
class SalaryStates(StatesGroup):
    waiting_for_group_choice  = State()
    waiting_for_option_choice = State()

# --- Админские состояния ---
class AdminStates(StatesGroup):
    menu = State()

# --- Состояния для UsersManagement (управление пользователями) ---
class UsersManagementStates(StatesGroup):
    waiting_for_user_selection = State()
    waiting_for_new_user_id    = State()
    waiting_for_delete_choice  = State()
    waiting_for_edit_choice    = State()
    waiting_for_new_name       = State()
    waiting_for_new_emoji      = State()
    waiting_for_balance_op     = State()
    waiting_for_balance_value  = State()

# --- Присваивание эмодзи (startemoji) ---
class EmojiStates(StatesGroup):
    waiting_for_assign = State()

# --- Состояния “очистки” (clean) ---
class CleanupStates(StatesGroup):
    waiting_for_main_menu    = State()
    waiting_for_group_choice = State()
    waiting_for_confirmation = State()

# --- Состояния Money (денежные операции) ---
class MoneyStates(StatesGroup):
    waiting_for_type         = State()
    waiting_for_group_choice = State()
    waiting_for_operation    = State()
    waiting_for_amount       = State()

# --- Состояния IDPhoto (получение file_id фотографии) ---
class IDPhotoStates(StatesGroup):
    waiting_photo = State()
