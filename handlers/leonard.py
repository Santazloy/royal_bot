# handlers/leonard.py

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from utils.bot_utils import safe_answer
from handlers.language import get_user_language, get_message
from handlers.group_id import show_group_id
from handlers.ai import list_models_for_menu
from handlers.states import IDPhotoStates

leonard_menu_router = Router()
PHOTO_ID = "photo/IMG_2585.JPG"

def build_leonard_menu(lang: str):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=get_message(lang, 'btn_group_id_raw'),
                callback_data="leonard_group_id"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_message(lang, 'btn_photo_id_raw'),
                callback_data="leonard_photo_id"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_message(lang, 'btn_ai_models_raw'),
                callback_data="leonard_ai_models"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_message(lang, 'btn_embeddings_raw'),
                callback_data="leonard_embeddings"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_message(lang, 'btn_report_raw'),
                callback_data="leonard_report"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_message(lang, 'btn_back_raw'),
                callback_data="leonard_back"
            )
        ],
    ])
    return kb

@leonard_menu_router.callback_query(lambda cb: cb.data == "leonard")
async def leonard_menu_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    kb = build_leonard_menu(lang)
    await safe_answer(
        callback,
        get_message(lang, 'leonard_header'),
        photo=PHOTO_ID,
        reply_markup=kb
    )

@leonard_menu_router.callback_query(lambda cb: cb.data == "leonard_group_id")
async def leonard_group_id_callback(callback: CallbackQuery, state: FSMContext):
    await show_group_id(callback.message)

@leonard_menu_router.callback_query(lambda cb: cb.data == "leonard_photo_id")
async def leonard_photo_id_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(
        callback,
        get_message(lang, 'photo_id_prompt')
    )
    await state.set_state(IDPhotoStates.waiting_photo)

@leonard_menu_router.callback_query(lambda cb: cb.data == "leonard_ai_models")
async def leonard_ai_models_callback(callback: CallbackQuery, state: FSMContext):
    await list_models_for_menu(callback)

@leonard_menu_router.callback_query(lambda cb: cb.data == "leonard_embeddings")
async def leonard_embeddings_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(
        callback,
        get_message(lang, 'embeddings_menu'),
        parse_mode="HTML",
        photo=PHOTO_ID
    )

@leonard_menu_router.callback_query(lambda cb: cb.data == "leonard_report")
async def leonard_report_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(
        callback,
        get_message(lang, 'report_menu'),
        parse_mode="HTML",
        photo=PHOTO_ID
    )

@leonard_menu_router.callback_query(lambda cb: cb.data == "leonard_back")
async def leonard_back_callback(callback: CallbackQuery, state: FSMContext):
    from handlers.menu_ad import show_admin_menu
    await show_admin_menu(callback.message, state)
