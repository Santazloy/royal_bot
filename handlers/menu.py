# handlers/menu.py

import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, InputMediaPhoto
)
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

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

# Глобальный словарь: {chat_id: message_id}, чтобы удалять старое меню
last_menu_message: dict[int, int] = {}

# file_id картинки (фото) для главного меню:
MENU_PHOTO_ID = "AgACAgQAAyEFAASJKijTAAIZ_mgjKdj-Sa3MdMHW-pSy_qLMhJOKAAJPxzEba90JUQfUH5f_fWYoAQADAgADeQADNgQ"


@menu_router.message(Command("menu"))
async def cmd_menu(message: Message):
    lang = await get_user_language(message.from_user.id)
    chat_id = message.chat.id

    # Удаляем предыдущее меню (если есть)
    old_msg_id = last_menu_message.get(chat_id)
    if old_msg_id:
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
        except Exception as e:
            logging.warning(f"Не удалось удалить старое меню в чате {chat_id}: {e}")

    # Кнопки меню
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=get_message(lang, "btn_booking"),
                callback_data="menu_stub|booking"
            ),
            InlineKeyboardButton(
                text=get_message(lang, "btn_girls"),
                callback_data="menu_stub|girls"
            ),
        ],
        [
            InlineKeyboardButton(
                text=get_message(lang, "btn_schedule"),
                callback_data="view_all_bookings"
            ),
            InlineKeyboardButton(
                text=get_message(lang, "btn_balance"),
                callback_data="menu_stub|balance"
            ),
        ],
        [
            InlineKeyboardButton(
                text=get_message(lang, "btn_news"),
                callback_data="menu_stub|news"
            ),
            InlineKeyboardButton(
                text=get_message(lang, "btn_cancel_booking"),
                callback_data="menu_stub|cancel_booking"
            ),
        ]
    ])

    # Отправляем новое меню (фото + кнопки)
    try:
        sent_msg = await message.answer_photo(
            photo=MENU_PHOTO_ID,
            reply_markup=kb
        )
        last_menu_message[chat_id] = sent_msg.message_id
    except Exception as e:
        logging.error(f"Не удалось отправить меню в чате {chat_id}: {e}")


@menu_router.callback_query(F.data.startswith("menu_stub|"))
async def on_menu_stub(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    parts = callback.data.split("|")
    if len(parts) != 2:
        return await callback.answer(get_message(lang, "invalid_data"), show_alert=True)

    action = parts[1]

    if action == "booking":
        # групповая клавиатура
        rows, buf = [], []
        for i, gk in enumerate(groups_data, start=1):
            buf.append(InlineKeyboardButton(
                text=gk, callback_data=f"bkgrp_{gk}"
            ))
            if i % 3 == 0:
                rows.append(buf); buf = []
        if buf: rows.append(buf)
        kb = InlineKeyboardMarkup(inline_keyboard=rows)

        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(media=GROUP_CHOICE_IMG, caption=""),
                reply_markup=kb
            )
        except TelegramBadRequest:
            try:
                await callback.message.delete()
            except: pass
            await callback.message.answer_photo(
                photo=GROUP_CHOICE_IMG,
                caption="",
                reply_markup=kb
            )

        await state.set_state(BookUserStates.waiting_for_group)
        await callback.answer()
        return

    elif action == "girls":
        await callback.answer(get_message(lang, "no_action"), show_alert=True)

    elif action == "news":
        header = get_message(lang, "news_header")
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(media=MENU_PHOTO_ID, caption=header),
                reply_markup=None
            )
        except TelegramBadRequest:
            try:
                await callback.message.delete()
            except: pass
            await callback.message.answer_photo(
                photo=MENU_PHOTO_ID,
                caption=header
            )
        await cmd_show_news(callback.message)
        await callback.answer()

    elif action == "balance":
        await callback.answer(get_message(lang, "no_action"), show_alert=True)

    elif action == "cancel_booking":
        await callback.answer(get_message(lang, "no_action"), show_alert=True)

    else:
        await callback.answer(get_message(lang, "menu_unknown"), show_alert=True)
