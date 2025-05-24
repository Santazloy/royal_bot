import logging

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.filters.command import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from handlers.language import get_user_language, get_message

logger = logging.getLogger(__name__)
menu_ad_router = Router()

# ========= Safe Answer =========
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

# ========= Admin Menu Keyboard (полный список) =========
def build_admin_menu_keyboard(lang):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_message(lang, 'btn_salary'), callback_data='ad_salary'),
                InlineKeyboardButton(text=get_message(lang, 'btn_money'), callback_data='ad_money'),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, 'btn_users'), callback_data='ad_users'),
                InlineKeyboardButton(text=get_message(lang, 'btn_news'), callback_data='ad_news'),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, 'btn_clean'), callback_data='ad_clean'),
                InlineKeyboardButton(text=get_message(lang, 'btn_balances'), callback_data='ad_balances'),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, 'btn_conversion'), callback_data='ad_conversion'),
                InlineKeyboardButton(text=get_message(lang, 'btn_embedding'), callback_data='ad_embedding'),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, 'btn_reset_day'), callback_data='ad_reset_day'),
                InlineKeyboardButton(text=get_message(lang, 'btn_emoji'), callback_data='ad_emoji'),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, 'btn_ai_models'), callback_data='ad_ai_models'),
                InlineKeyboardButton(text=get_message(lang, 'btn_rules'), callback_data='ad_rules'),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, 'btn_photo_id'), callback_data='ad_photo_id'),
                InlineKeyboardButton(text=get_message(lang, 'btn_group_id'), callback_data='ad_group_id'),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, 'btn_back'), callback_data='ad_back')
            ],
        ]
    )

# ========= Admin Menu Entry =========
@menu_ad_router.message(Command("ad"))
async def admin_menu_cmd(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.from_user.id not in ADMIN_IDS:
        return await safe_answer(message, get_message(lang, "admin_only"))
    kb = build_admin_menu_keyboard(lang)
    await safe_answer(
        message,
        get_message(lang, "menu_admin_header", default="Меню администратора:"),
        reply_markup=kb
    )
    await state.set_state("admin_menu")

# ========= Admin Menu Callbacks =========
@menu_ad_router.callback_query(F.data.startswith("ad_"), StateFilter("admin_menu"))
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if callback.from_user.id not in ADMIN_IDS:
        return await safe_answer(callback, get_message(lang, "admin_only"), show_alert=True)
    data = callback.data

    if data == "ad_salary":
        await safe_answer(callback, get_message(lang, "salary_choose_group"))
    elif data == "ad_money":
        await safe_answer(callback, get_message(lang, "choose_what_change"))
    elif data == "ad_users":
        await safe_answer(callback, get_message(lang, "menu_users_header", default="Управление пользователями"))
    elif data == "ad_news":
        await safe_answer(callback, get_message(lang, "news_header"))
    elif data == "ad_clean":
        await safe_answer(callback, get_message(lang, "clean_prompt"))
    elif data == "ad_balances":
        await safe_answer(callback, get_message(lang, "menu_balances_header", default="Балансы"))
    elif data == "ad_conversion":
        await safe_answer(callback, get_message(lang, "menu_conversion_header", default="Конвертация"))
    elif data == "ad_embedding":
        await safe_answer(callback, get_message(lang, "menu_embedding_header", default="Эмбеддинг"))
    elif data == "ad_reset_day":
        await safe_answer(callback, get_message(lang, "menu_reset_day_header", default="Сброс дня"))
    elif data == "ad_emoji":
        await safe_answer(callback, get_message(lang, "menu_emoji_header", default="Эмодзи"))
    elif data == "ad_ai_models":
        await safe_answer(callback, get_message(lang, "menu_ai_models_header", default="AI Модели"))
    elif data == "ad_rules":
        await safe_answer(callback, get_message(lang, "menu_rules_header", default="Правила"))
    elif data == "ad_photo_id":
        await safe_answer(callback, get_message(lang, "menu_photo_id_header", default="Фото ID"))
    elif data == "ad_group_id":
        await safe_answer(callback, get_message(lang, "menu_group_id_header", default="Группа ID"))
    elif data == "ad_back":
        await safe_answer(callback, get_message(lang, "menu_back", default="Главное меню"))
        await state.clear()
    else:
        await safe_answer(callback, get_message(lang, "menu_unknown"))
    await callback.answer()

# ========= Добавь эти ключи в TRANSLATIONS, если хочешь красивые заголовки =========
# 'menu_admin_header', 'menu_users_header', 'menu_balances_header', 'menu_conversion_header',
# 'menu_embedding_header', 'menu_reset_day_header', 'menu_emoji_header', 'menu_ai_models_header',
# 'menu_rules_header', 'menu_photo_id_header', 'menu_group_id_header', 'menu_back'

# ========= Router Setup =========
def setup_menu_ad_router(dp):
    dp.include_router(menu_ad_router)
