import logging

from aiogram import Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.filters.command import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from handlers.language import get_user_language, get_message

from handlers.news import cmd_added
from handlers.salary import cmd_salary
from handlers.group_id import show_group_id
from handlers.startemoji import cmd_emoji
from handlers.money import money_command
from handlers.clean import cmd_clean
from handlers.booking.cancelbook import cmd_off_admin

logger = logging.getLogger(__name__)
menu_ad_router = Router()

async def safe_answer(message_or_callback, text, **kwargs):
    fallback = "Ошибка: текст не найден"
    if not text or not str(text).strip():
        logger.error(f"[safe_answer] Пустой текст: {text!r}, kwargs={kwargs}")
        text = fallback
    if hasattr(message_or_callback, 'answer'):
        return await message_or_callback.answer(text, **kwargs)
    if hasattr(message_or_callback, 'edit_text'):
        return await message_or_callback.edit_text(text, **kwargs)
    raise RuntimeError("safe_answer: не могу отправить текст")

def build_admin_menu_keyboard(lang):
    # Список кнопок (text, callback_data)
    buttons = [
        (get_message(lang, 'btn_news'), 'added'),
        (get_message(lang, 'btn_salary'), 'salary'),
        (get_message(lang, 'btn_group_id'), 'chat'),
        (get_message(lang, 'btn_emoji'), 'emoji'),
        (get_message(lang, 'btn_photo_id'), 'photo_admin'),  # <-- кнопка Фото рядом с эмодзи
        (get_message(lang, 'btn_money'), 'money'),
        (get_message(lang, 'btn_cancel_booking'), 'offad'),
        (get_message(lang, 'btn_clean'), 'clean'),
        (get_message(lang, 'btn_balances'), 'balances'),
        (get_message(lang, 'btn_rules'), 'rules'),
        (get_message(lang, 'btn_ai_models'), 'ai_models'),
        (get_message(lang, 'btn_users'), 'users'),
        (get_message(lang, 'btn_conversion'), 'conversion'),
        (get_message(lang, 'btn_embedding'), 'embedding'),
        (get_message(lang, 'btn_reset_day'), 'reset_day'),
        (get_message(lang, 'btn_back'), 'back'),
    ]
    # Формируем по 2 в строке
    inline_keyboard = []
    for i in range(0, len(buttons), 2):
        row = []
        for b in buttons[i:i+2]:
            row.append(InlineKeyboardButton(text=b[0], callback_data=b[1]))
        inline_keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

@menu_ad_router.message(Command("ad"))
async def admin_menu_cmd(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    # ---- ДЕБАГ: выводим в консоль и в чат ----
    print("DEBUG | ADMIN_IDS:", ADMIN_IDS)
    print("DEBUG | CURRENT USER:", message.from_user.id)
    await message.answer(f"DEBUG | ADMIN_IDS: {ADMIN_IDS}\nDEBUG | CURRENT USER: {message.from_user.id}")
    # ---- Проверка админа ----
    if message.from_user.id not in ADMIN_IDS:
        return await safe_answer(message, get_message(lang, "admin_only"))
    kb = build_admin_menu_keyboard(lang)
    await safe_answer(
        message,
        get_message(lang, "menu_admin_header", default="Меню администратора:"),
        reply_markup=kb
    )
    await state.set_state("admin_menu")

@menu_ad_router.callback_query(StateFilter("admin_menu"))
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await safe_answer(callback, get_message(lang, "admin_only"), show_alert=True)
    data = callback.data

    if data == "added":
        await cmd_added(callback.message, state)
    elif data == "salary":
        await cmd_salary(callback.message, state)
    elif data == "chat":
        await show_group_id(callback.message)
    elif data == "emoji":
        await cmd_emoji(callback.message)
    elif data == "photo_admin":
        await safe_answer(callback, "Панель работы с фото для админа (реализуй свою логику)")
    elif data == "money":
        await money_command(callback.message, state)
    elif data == "offad":
        await cmd_off_admin(callback.message)
    elif data == "clean":
        await cmd_clean(callback.message, state)
    elif data == "balances":
        await safe_answer(callback, get_message(lang, "menu_balances_header", default="Балансы (ещё не реализовано)"))
    elif data == "rules":
        await safe_answer(callback, get_message(lang, "menu_rules_header", default="Правила (ещё не реализовано)"))
    elif data == "ai_models":
        await safe_answer(callback, get_message(lang, "menu_ai_models_header", default="AI Модели (ещё не реализовано)"))
    elif data == "users":
        await safe_answer(callback, get_message(lang, "menu_users_header", default="Пользователи (ещё не реализовано)"))
    elif data == "conversion":
        await safe_answer(callback, get_message(lang, "menu_conversion_header", default="Конвертация (ещё не реализовано)"))
    elif data == "embedding":
        await safe_answer(callback, get_message(lang, "menu_embedding_header", default="Эмбеддинг (ещё не реализовано)"))
    elif data == "reset_day":
        await safe_answer(callback, get_message(lang, "menu_reset_day_header", default="Сброс дня (ещё не реализовано)"))
    elif data == "back":
        await safe_answer(callback, "Выход из админ-меню.")
        await state.clear()
    else:
        await safe_answer(callback, "Неизвестная команда.")
    await callback.answer()
