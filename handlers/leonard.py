# handlers/leonard.py

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from utils.bot_utils import safe_answer
from handlers.language import get_user_language

leonard_menu_router = Router()
PHOTO_ID = "photo/IMG_2585.JPG"

def build_leonard_menu(lang: str):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 ID группы", callback_data="leonard_group_id")],
        [InlineKeyboardButton(text="📷 ID фото", callback_data="leonard_photo_id")],
        [InlineKeyboardButton(text="🦾 Модели ИИ", callback_data="leonard_ai_models")],
        [InlineKeyboardButton(text="🗃 Эмбеддинги", callback_data="leonard_embeddings")],
        [InlineKeyboardButton(text="🧾 Отчет", callback_data="leonard_report")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="leonard_back")],
    ])
    return kb

@leonard_menu_router.callback_query(lambda cb: cb.data == "leonard")
async def leonard_menu_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    kb = build_leonard_menu(lang)
    await safe_answer(callback, "🐆 Леонард — меню:", photo=PHOTO_ID, reply_markup=kb)

@leonard_menu_router.callback_query(lambda cb: cb.data in {
    "leonard_group_id", "leonard_photo_id", "leonard_ai_models", "leonard_embeddings", "leonard_emoji"
})
async def leonard_submenu_callback(callback: CallbackQuery, state: FSMContext):
    responses = {
        "leonard_group_id": "💬 <b>ID группы:</b> Тут будет функция вывода/поиска ID группы.",
        "leonard_photo_id": "📷 <b>ID фото:</b> Тут будет функция получения ID фото.",
        "leonard_ai_models": "🦾 <b>Модели ИИ:</b> Тут будет список/работа с моделями.",
        "leonard_embeddings": "🗃 <b>Эмбеддинги:</b> Тут будет меню для работы с эмбеддингами.",
        "leonard_emoji": "🧾 <b>Отчет:</b> Тут будет отправка отчета.",
    }
    text = responses.get(callback.data, "Нет данных.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="leonard_back")]
    ])
    await safe_answer(callback, text, photo=PHOTO_ID, parse_mode="HTML", reply_markup=kb)

@leonard_menu_router.callback_query(lambda cb: cb.data == "leonard_back")
async def leonard_back_callback(callback: CallbackQuery, state: FSMContext):
    from handlers.menu_ad import show_admin_menu
    await show_admin_menu(callback.message, state)
