# handlers/menu.py

import logging
from aiogram import Router, F, types
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, InputMediaPhoto
)
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

# Правильные импорты констант и стейтов
from constants.booking_const import (
    groups_data,
    GROUP_CHOICE_IMG,
    DAY_CHOICE_IMG,
    TIME_CHOICE_IMG,
    FINAL_BOOKED_IMG,
)
from app_states import BookUserStates

from handlers.news import cmd_show_news

menu_router = Router()

# Глобальный словарь: {chat_id: message_id}, чтобы удалять старое меню
last_menu_message = {}

# file_id картинки (фото) для главного меню:
MENU_PHOTO_ID = "AgACAgQAAyEFAASJKijTAAIZ_mgjKdj-Sa3MdMHW-pSy_qLMhJOKAAJPxzEba90JUQfUH5f_fWYoAQADAgADeQADNgQ"


@menu_router.message(Command("menu"))
async def cmd_menu(message: Message):
    chat_id = message.chat.id

    # Удаляем предыдущее меню (если есть)
    old_msg_id = last_menu_message.get(chat_id)
    if old_msg_id:
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
        except Exception as e:
            logging.warning(f"Не удалось удалить старое меню в чате {chat_id}: {e}")

    # Клавиатура: 2 колонки × 3 строки (6 кнопок)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏰ Booking / 预约", callback_data="menu_stub|booking"),
            InlineKeyboardButton(text="💃 Girls / 女孩",  callback_data="menu_stub|girls"),
        ],
        [
            # Здесь уже callback_data="view_all_bookings"
            InlineKeyboardButton(text="📋 All Booking / 所有预约", callback_data="view_all_bookings"),
            InlineKeyboardButton(text="🧮 Balance / 余额",        callback_data="menu_stub|balance"),
        ],
        [
            InlineKeyboardButton(text="📰 News / 新闻", callback_data="menu_stub|news"),
            InlineKeyboardButton(text="❌ Cancel Booking / 取消预约", callback_data="menu_stub|cancel_booking"),
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
    """
    Обрабатывает нажатия на кнопки, где callback_data начинается с "menu_stub|..."
    Если action == "booking", то показываем выбор группы и т.д.
    """
    parts = callback.data.split("|")
    if len(parts) != 2:
        return await callback.answer("Некорректные данные!", show_alert=True)

    action = parts[1]

    if action == "booking":
        # Открываем клавиатуру выбора групп
        row_buf = []
        rows = []
        i = 0
        for gk in groups_data.keys():
            row_buf.append(InlineKeyboardButton(text=gk, callback_data=f"bkgrp_{gk}"))
            i += 1
            if i % 3 == 0:
                rows.append(row_buf)
                row_buf = []
        if row_buf:
            rows.append(row_buf)

        kb = InlineKeyboardMarkup(inline_keyboard=rows)

        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=GROUP_CHOICE_IMG,
                    caption=""
                ),
                reply_markup=kb
            )
        except TelegramBadRequest as e:
            logging.warning(f"Edit media failed: {e}")
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer_photo(
                photo=GROUP_CHOICE_IMG,
                caption="",
                reply_markup=kb
            )

        await state.set_state(BookUserStates.waiting_for_group)
        await callback.answer()
        return

    elif action == "girls":
        await callback.answer("Заглушка: список Girls...", show_alert=True)
    elif action == "news":
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=MENU_PHOTO_ID,
                    caption="Последние новости:"
                ),
                reply_markup=None
            )
        except TelegramBadRequest as e:
            logging.warning(f"Edit media failed: {e}")
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer_photo(
                photo=MENU_PHOTO_ID,
                caption="Последние новости:"
            )
        # Показываем все новости
        await cmd_show_news(callback.message)
        await callback.answer()
    elif action == "balance":
        await callback.answer("Заглушка: показ баланса...", show_alert=True)
    elif action == "cancel_booking":
        await callback.answer("Заглушка: отмена бронирования...", show_alert=True)
    else:
        await callback.answer("Неизвестная команда меню!", show_alert=True)