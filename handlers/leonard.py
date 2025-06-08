# handlers/leonard.py

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import is_user_admin
from utils.bot_utils import safe_answer
from handlers.language import get_user_language, get_message
from handlers.group_id import show_group_id
from handlers.ai import list_models_for_menu
from handlers.states import IDPhotoStates

leonard_menu_router = Router()
PHOTO_ID = "photo/IMG_2585.JPG"

# 1) Любой callback от не-админа — только alert
@leonard_menu_router.callback_query(lambda cb: not is_user_admin(cb.from_user.id))
async def _deny_non_admin(cb: CallbackQuery):
    await cb.answer("⚠️ У вас нет прав для выполнения этого действия", show_alert=True)


def build_leonard_menu(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_message(lang, 'btn_group_id_raw'), callback_data="leonard_group_id")],
        [InlineKeyboardButton(text=get_message(lang, 'btn_photo_id_raw'), callback_data="leonard_photo_id")],
        [InlineKeyboardButton(text=get_message(lang, 'btn_ai_models_raw'), callback_data="leonard_ai_models")],
        [InlineKeyboardButton(text=get_message(lang, 'btn_embeddings_raw'), callback_data="leonard_embeddings")],
        [InlineKeyboardButton(text=get_message(lang, 'btn_report_raw'), callback_data="leonard_report")],
        [InlineKeyboardButton(text=get_message(lang, 'btn_back_raw'), callback_data="leonard_back")],
    ])


@leonard_menu_router.callback_query(lambda cb: is_user_admin(cb.from_user.id), F.data == "leonard")
async def leonard_menu_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    kb = build_leonard_menu(lang)
    await safe_answer(
        callback,
        get_message(lang, 'leonard_header'),
        photo=PHOTO_ID,
        reply_markup=kb
    )


@leonard_menu_router.callback_query(lambda cb: is_user_admin(cb.from_user.id), F.data == "leonard_group_id")
async def leonard_group_id_callback(callback: CallbackQuery, state: FSMContext):
    await show_group_id(callback.message)


@leonard_menu_router.callback_query(lambda cb: is_user_admin(cb.from_user.id), F.data == "leonard_photo_id")
async def leonard_photo_id_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(
        callback,
        get_message(lang, 'photo_id_prompt')
    )
    await state.set_state(IDPhotoStates.waiting_photo)


@leonard_menu_router.callback_query(lambda cb: is_user_admin(cb.from_user.id), F.data == "leonard_ai_models")
async def leonard_ai_models_callback(callback: CallbackQuery, state: FSMContext):
    await list_models_for_menu(callback)


@leonard_menu_router.callback_query(lambda cb: is_user_admin(cb.from_user.id), F.data == "leonard_embeddings")
async def leonard_embeddings_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(
        callback,
        get_message(lang, 'embeddings_menu'),
        parse_mode="HTML",
        photo=PHOTO_ID
    )


@leonard_menu_router.callback_query(lambda cb: is_user_admin(cb.from_user.id), F.data == "leonard_report")
async def leonard_report_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(
        callback,
        get_message(lang, 'report_menu'),
        parse_mode="HTML",
        photo=PHOTO_ID
    )


@leonard_menu_router.callback_query(lambda cb: is_user_admin(cb.from_user.id), F.data == "leonard_back")
async def leonard_back_callback(callback: CallbackQuery, state: FSMContext):
    from handlers.menu_ad import show_admin_menu
    await show_admin_menu(callback.message, state)
