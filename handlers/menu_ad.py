# handlers/menu_ad.py

import logging
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.bot_utils import safe_answer
from config import is_user_admin
from handlers.language import get_user_language, get_message
from states.admin_states import AdminStates

from handlers.clean import cmd_clean, clean_via_button
from handlers.salary import salary_command
from handlers.startemoji import cmd_emoji
from handlers.money import money_command
from handlers.booking.cancelbook import cmd_off_admin
from handlers.leonard import leonard_menu_callback  # Новый модуль

last_admin_menu_message: dict[int, int] = {}

PHOTO_ID = "photo/IMG_2585.JPG"
EMOJI_MAP = {
    'salary': '💰',
    'emoji': '😊',
    'money': '💵',
    'offad': '❌',
    'clean': '🧹',
    'balances': '📊',
    'rules': '📜',
    'conversion': '🔄',
    'reset_day': '🔁',
    'back': '🔙',
    'leonard': '🐆',
}

logger = logging.getLogger(__name__)
menu_ad_router = Router()

def build_admin_menu_keyboard(lang: str):
    buttons = [
        (get_message(lang, 'menu_leonard', default='Леонард'), 'leonard'),
        (get_message(lang, 'btn_salary'),         'salary'),
        (get_message(lang, 'btn_emoji'),          'emoji'),
        (get_message(lang, 'btn_money'),          'money'),
        (get_message(lang, 'btn_cancel_booking'), 'offad'),
        (get_message(lang, 'btn_clean'),          'clean'),
        (get_message(lang, 'btn_balances'),       'balances'),
        (get_message(lang, 'btn_rules'),          'rules'),
        (get_message(lang, 'btn_conversion'),     'conversion'),
        (get_message(lang, 'btn_reset_day'),      'reset_day'),
        (get_message(lang, 'btn_back'),           'back'),
    ]
    builder = InlineKeyboardBuilder()
    for text, data in buttons:
        emoji = EMOJI_MAP.get(data, '')
        builder.button(text=f"{emoji} {text}", callback_data=data)
    builder.adjust(2)
    return builder.as_markup()

@menu_ad_router.message(Command('ad'))
async def show_admin_menu(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if not is_user_admin(message.from_user.id):
        return await safe_answer(message, get_message(lang, 'admin_only'))
    chat_id = message.chat.id
    prev_id = last_admin_menu_message.get(chat_id)
    if prev_id:
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=prev_id)
        except:
            pass
    kb = build_admin_menu_keyboard(lang)
    sent = await safe_answer(
        message,
        photo=PHOTO_ID,
        caption=get_message(lang, 'menu_admin_header', default='Меню администратора:'),
        reply_markup=kb
    )
    last_admin_menu_message[chat_id] = sent.message_id
    await state.set_state(AdminStates.menu)

@menu_ad_router.callback_query(AdminStates.menu)
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    lang   = await get_user_language(callback.from_user.id)
    action = callback.data
    if not is_user_admin(callback.from_user.id):
        return await safe_answer(callback, get_message(lang, 'admin_only'), show_alert=True)
    if action == 'leonard':
        return await leonard_menu_callback(callback, state)
    if action == 'salary':
        return await salary_command(callback.message, state)
    if action == 'emoji':
        return await cmd_emoji(callback.message, callback.bot)
    if action == 'money':
        return await money_command(callback.message, state)
    if action == 'offad':
        return await cmd_off_admin(callback.message)
    if action == 'clean':
        return await clean_via_button(callback, state)
    if action in ('balances','rules','conversion','reset_day'):
        key = f'menu_{action}_header'
        return await safe_answer(callback, get_message(lang, key, default='Не реализовано'))
    if action == 'back':
        await safe_answer(callback, get_message(lang, 'menu_back_confirm', default='Выход из админ-меню.'))
        return await state.clear()
    return await safe_answer(callback, get_message(lang, 'menu_unknown_command', default='Неизвестная команда.'))
