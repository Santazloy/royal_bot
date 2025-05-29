import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, InputMediaPhoto
)
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext

from utils.bot_utils import safe_answer
from constants.booking_const import (
    groups_data,
    GROUP_CHOICE_IMG,
    DAY_CHOICE_IMG,
    TIME_CHOICE_IMG,
    FINAL_BOOKED_IMG,
)
from app_states import BookUserStates
from handlers.language import get_user_language, get_message
from handlers.news import cmd_show_news

menu_router = Router()

MENU_PHOTO_ID = "AgACAgUAAyEFAASgiEpFAAMMaDifEmRyoCT31UlSUzMioMqQkRcAAuPMMRsda7hV537I3mD5jpQBAAMCAAN5AAM2BA"

@menu_router.message(Command("menu"))
async def cmd_menu(message: Message):
    lang = await get_user_language(message.from_user.id)
    chat_id = message.chat.id

    try:
        await safe_answer(message, photo=MENU_PHOTO_ID, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=get_message(lang, "menu_btn_booking"),    callback_data="menu_stub|booking"),
                InlineKeyboardButton(text=get_message(lang, "menu_btn_girls"),      callback_data="menu_stub|girls"),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, "menu_btn_schedule"),   callback_data="view_all_bookings"),
                InlineKeyboardButton(text=get_message(lang, "menu_btn_balance"),    callback_data="menu_stub|balance"),
            ],
            [
                InlineKeyboardButton(text=get_message(lang, "menu_btn_news"),       callback_data="menu_stub|news"),
                InlineKeyboardButton(text=get_message(lang, "menu_btn_cancel_booking"), callback_data="menu_stub|cancel_booking"),
            ],
        ]))
    except Exception as e:
        logging.error(f"Не удалось отправить меню в чате {chat_id}: {e}")

@menu_router.callback_query(F.data.startswith("menu_stub|"))
async def on_menu_stub(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("|")
    if len(parts) != 2:
        await safe_answer(callback, photo=MENU_PHOTO_ID, caption=get_message(lang, "invalid_data"))
        return

    action = parts[1]

    if action == "booking":
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

    elif action == "girls":
        await safe_answer(callback, photo=MENU_PHOTO_ID, caption=get_message(lang, "menu_no_action"))

    elif action == "news":
        header = get_message(lang, "menu_news_header")
        try:
            await callback.message.delete()
        except:
            pass
        await safe_answer(callback, photo=MENU_PHOTO_ID, caption=header)
        await cmd_show_news(callback.message)

    elif action == "balance":
        await safe_answer(callback, photo=MENU_PHOTO_ID, caption=get_message(lang, "menu_no_action"))

    elif action == "cancel_booking":
        await safe_answer(callback, photo=MENU_PHOTO_ID, caption=get_message(lang, "menu_no_action"))

    else:
        await safe_answer(callback, photo=MENU_PHOTO_ID, caption=get_message(lang, "menu_unknown"))
