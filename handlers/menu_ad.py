# handlers/menu_ad.py

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import is_user_admin
from handlers.language import get_user_language, get_message
from states.admin_states import AdminStates

from handlers.news import cmd_added, added_via_button
from handlers.clean import cmd_clean, clean_via_button
from handlers.salary import salary_command
from handlers.group_id import show_group_id
from handlers.startemoji import cmd_emoji, emoji_via_button
from handlers.money import money_command
from handlers.booking.cancelbook import cmd_off_admin

logger = logging.getLogger(__name__)
menu_ad_router = Router()

def build_admin_menu_keyboard(lang: str):
    buttons = [
        (get_message(lang, 'btn_news'),           'added'),
        (get_message(lang, 'btn_salary'),         'salary'),
        (get_message(lang, 'btn_group_id'),       'chat'),
        (get_message(lang, 'btn_emoji'),          'emoji'),
        (get_message(lang, 'btn_photo_id'),       'photo_admin'),
        (get_message(lang, 'btn_money'),          'money'),
        (get_message(lang, 'btn_cancel_booking'), 'offad'),
        (get_message(lang, 'btn_clean'),          'clean'),
        (get_message(lang, 'btn_balances'),       'balances'),
        (get_message(lang, 'btn_rules'),          'rules'),
        (get_message(lang, 'btn_ai_models'),      'ai_models'),
        (get_message(lang, 'btn_users'),          'users'),
        (get_message(lang, 'btn_conversion'),     'conversion'),
        (get_message(lang, 'btn_embedding'),      'embedding'),
        (get_message(lang, 'btn_reset_day'),      'reset_day'),
        (get_message(lang, 'btn_back'),           'back'),
    ]
    builder = InlineKeyboardBuilder()
    for text, data in buttons:
        builder.button(text=text, callback_data=data)
    builder.adjust(2)
    return builder.as_markup()

async def safe_answer(entity, text: str, **kwargs):
    if not text or not text.strip():
        logger.error(f"[safe_answer] Empty text: {text!r}")
        text = "Ошибка: текст не найден"
    if isinstance(entity, CallbackQuery):
        return await entity.message.answer(text, **kwargs)
    return await entity.answer(text, **kwargs)

@menu_ad_router.message(Command('ad'))
async def show_admin_menu(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if not is_user_admin(message.from_user.id):
        return await safe_answer(message, get_message(lang, 'admin_only'))

    kb = build_admin_menu_keyboard(lang)
    await safe_answer(
        message,
        get_message(lang, 'menu_admin_header', default='Меню администратора:'),
        reply_markup=kb
    )
    await state.set_state(AdminStates.menu)

@menu_ad_router.callback_query(AdminStates.menu)
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    lang   = await get_user_language(callback.from_user.id)
    action = callback.data

    if not is_user_admin(callback.from_user.id):
        return await callback.answer(get_message(lang, 'admin_only'), show_alert=True)

    # сразу убираем спиннер
    await callback.answer()

    if action == 'added':
        return await added_via_button(callback, state)

    if action == 'salary':
        return await salary_command(callback.message, state)

    if action == 'chat':
        return await show_group_id(callback.message)

    if action == 'emoji':
        return await emoji_via_button(callback, state)

    if action == 'photo_admin':
        return await safe_answer(callback, 'Панель работы с фото (не реализовано)')

    if action == 'money':
        return await money_command(callback.message, state)

    if action == 'offad':
        return await cmd_off_admin(callback.message)

    if action == 'clean':
        return await clean_via_button(callback, state)

    if action in ('balances','rules','ai_models','users','conversion','embedding','reset_day'):
        key = f'menu_{action}_header'
        return await safe_answer(callback, get_message(lang, key, default='Не реализовано'))

    if action == 'back':
        await safe_answer(callback, get_message(lang, 'menu_back_confirm', default='Выход из админ-меню.'))
        return await state.clear()

    # fallback
    await safe_answer(callback, get_message(lang, 'menu_unknown_command', default='Неизвестная команда.'))
