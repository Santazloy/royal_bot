import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.bot_utils import safe_answer
from config import is_user_admin
from handlers.language import get_user_language, get_message
from handlers.states import AdminStates

from handlers.clean import cmd_clean, clean_via_button
from handlers.salary import salary_command
from handlers.startemoji import cmd_emoji
from handlers.money import money_command
from handlers.booking.cancelbook import cmd_off_admin
from handlers.leonard import leonard_menu_callback
from handlers.users import show_users_via_callback
from handlers.next import prompt_reset_day

logger = logging.getLogger(__name__)
menu_ad_router = Router()
last_admin_menu_message: dict[int, int] = {}

PHOTO_ID = "photo/IMG_2585.JPG"
EMOJI_MAP = {
    "leonard":    "🐆",
    "salary":     "💰",
    "emoji":      "😊",
    "money":      "💵",
    "offad":      "❌",
    "clean":      "🧹",
    "balances":   "📊",
    "rules":      "📜",
    "conversion": "🔄",
    "reset_day":  "🔁",
    "back":       "🔙",
}

# 1) Callback от не-админа — только alert
@menu_ad_router.callback_query(lambda cb: not is_user_admin(cb.from_user.id))
async def _deny_non_admin_cb(cb: CallbackQuery):
    await cb.answer("⚠️ У вас нет прав для выполнения этого действия", show_alert=True)

# 2) /ad от не-админа — тихий отказ
@menu_ad_router.message(lambda m: not is_user_admin(m.from_user.id), Command("ad"))
async def _deny_ad_cmd(message: Message):
    return

# 3) /ad — только для админов
@menu_ad_router.message(Command("ad"))
async def show_admin_menu(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    chat_id = message.chat.id
    prev_id = last_admin_menu_message.get(chat_id)
    if prev_id:
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=prev_id)
        except:
            pass

    buttons = [
        (get_message(lang, "menu_leonard", default="Леонард"),      "leonard"),
        (get_message(lang, "btn_salary",   default="Зарплата"),     "salary"),
        (get_message(lang, "btn_emoji",    default="Эмодзи"),       "emoji"),
        (get_message(lang, "btn_money",    default="Деньги"),       "money"),
        (get_message(lang, "btn_cancel_booking", default="Отмена брони"), "offad"),
        (get_message(lang, "btn_clean",    default="Очистка"),      "clean"),
        (get_message(lang, "btn_balances", default="Балансы"),      "balances"),
        (get_message(lang, "btn_rules",    default="Правила"),      "rules"),
        (get_message(lang, "btn_conversion", default="Конвертация"), "conversion"),
        (get_message(lang, "btn_reset_day", default="Сброс дня"),    "reset_day"),
        (get_message(lang, "btn_back",     default="« Назад"),      "back"),
    ]
    builder = InlineKeyboardBuilder()
    for text, data in buttons:
        emoji = EMOJI_MAP.get(data, "")
        builder.button(text=f"{emoji} {text}", callback_data=data)
    markup = builder.adjust(2).as_markup()

    sent = await safe_answer(
        message,
        photo=PHOTO_ID,
        caption=get_message(lang, "menu_admin_header", default="Меню администратора:"),
        reply_markup=markup,
    )
    last_admin_menu_message[chat_id] = sent.message_id
    await state.set_state(AdminStates.menu)

# 4) Обработчик нажатий админ-меню — только админам
@menu_ad_router.callback_query(AdminStates.menu)
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    me = await callback.bot.get_me()
    if callback.from_user.id == me.id:
        return

    lang = await get_user_language(callback.from_user.id)
    action = callback.data

    if action == "leonard":
        return await leonard_menu_callback(callback, state)
    if action == "salary":
        return await salary_command(callback.message, state)
    if action == "emoji":
        return await cmd_emoji(callback, callback.bot)
    if action == "money":
        return await money_command(callback.message, state)
    if action == "offad":
        return await cmd_off_admin(callback.message)
    if action == "clean":
        return await clean_via_button(callback, state)
    if action == "balances":
        return await show_users_via_callback(callback, state)
    if action == "rules":
        from handlers.rules import callback_rules
        return await callback_rules(callback)
    if action == "conversion":
        from handlers.exchange import callback_conversion
        return await callback_conversion(callback, state)

    if action == "reset_day":
        return await prompt_reset_day(callback)

    if action == "back":
        await safe_answer(callback, get_message(lang, "menu_back_confirm", default="Выход из админ-меню."))
        return await state.clear()

    return await safe_answer(
        callback, get_message(lang, "menu_unknown_command", default="Неизвестная команда.")
    )
