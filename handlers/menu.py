# handlers/menu.py

import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext

from utils.bot_utils import safe_answer
from constants.booking_const import (
    groups_data,
    GROUP_CHOICE_IMG,
)
from app_states import BookUserStates
from handlers.language import get_user_language, get_message

menu_router = Router()

MENU_PHOTO_ID = "photo/IMG_2585.JPG"

@menu_router.message(Command("menu"))
async def cmd_menu(message: Message):
    lang = await get_user_language(message.from_user.id)
    try:
        await safe_answer(message, photo=MENU_PHOTO_ID, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=get_message(lang, "menu_btn_booking"), callback_data="menu_stub|booking"),
                InlineKeyboardButton(text=get_message(lang, "menu_btn_girls"), callback_data="menu_stub|girls"),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, "menu_btn_schedule"), callback_data="view_all_bookings"),
                InlineKeyboardButton(text=get_message(lang, "menu_btn_balance"), callback_data="menu_stub|balance"),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, "menu_btn_news"), callback_data="menu_stub|news"),
                InlineKeyboardButton(text=get_message(lang, "menu_btn_cancel_booking"), callback_data="menu_stub|cancel_booking"),
            ],
        ]))
    except Exception as e:
        logging.error(f"Не удалось отправить меню: {e}")

@menu_router.callback_query(F.data == "menu_stub|booking")
async def on_menu_stub_booking(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    rows, buf = [], []
    for i, gk in enumerate(groups_data, start=1):
        buf.append(InlineKeyboardButton(text=gk, callback_data=f"bkgrp_{gk}"))
        if i % 3 == 0:
            rows.append(buf); buf = []
    if buf:
        rows.append(buf)
    try:
        await callback.message.delete()
    except:
        pass
    await safe_answer(callback, photo=GROUP_CHOICE_IMG, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await state.set_state(BookUserStates.waiting_for_group)

@menu_router.callback_query(F.data == "menu_stub|girls")
async def on_menu_stub_girls(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(callback, photo=MENU_PHOTO_ID, caption=get_message(lang, "menu_no_action"))

@menu_router.callback_query(F.data == "menu_stub|balance")
async def on_menu_stub_balance(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(callback, photo=MENU_PHOTO_ID, caption=get_message(lang, "menu_no_action"))

@menu_router.callback_query(F.data == "menu_stub|news")
async def on_menu_stub_news(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    header = get_message(lang, "menu_news_header")
    try:
        await callback.message.delete()
    except:
        pass
    await safe_answer(callback, photo=MENU_PHOTO_ID, caption=header)
    from handlers.news import cmd_show_news
    await cmd_show_news(callback.message)

@menu_router.callback_query(F.data == "menu_stub|cancel_booking")
async def on_menu_stub_cancel_booking(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(callback, photo=MENU_PHOTO_ID, caption=get_message(lang, "menu_no_action"))

@menu_router.callback_query(~(
    (F.data == "menu_stub|booking") |
    (F.data == "menu_stub|girls") |
    (F.data == "menu_stub|balance") |
    (F.data == "menu_stub|news") |
    (F.data == "menu_stub|cancel_booking") |
    (F.data == "view_all_bookings")
))
async def on_menu_stub_unknown(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    await safe_answer(callback, photo=MENU_PHOTO_ID, caption=get_message(lang, "menu_unknown"))
