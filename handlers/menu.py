# handlers/menu.py

import logging
from aiogram import Router, F, types
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

# Импортируем из booking.py то, что нужно:
from handlers.booking import groups_data, BookUserStates, BOOKING_PHOTO_ID
from handlers.news import cmd_show_news
menu_router = Router()

# Глобальный словарь: {chat_id: message_id}, чтобы удалять старое меню
last_menu_message = {}

# file_id картинки (фото) для главного меню:
MENU_PHOTO_ID = "AgACAgUAAyEFAASVOrsCAAPIaCLmhi308A24UzDBSEx2jLW7VrkAAofEMRsGphlVmJQawyQ2FOIBAAMCAAN5AAM2BA"


@menu_router.message(Command("menu"))
async def cmd_menu(message: Message):
    """
    При вызове /menu:
    1) Удаляем предыдущее меню (если хранится в last_menu_message)
    2) Отправляем новое сообщение с картинкой и двухколоночной клавиатурой
    3) Сохраняем message_id
    """
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
            InlineKeyboardButton(text="📋 All Booking / 所有预约", callback_data="menu_stub|all_booking"),
            InlineKeyboardButton(text="🧮 Balance / 余额",        callback_data="menu_stub|balance"),
        ],
        [
            InlineKeyboardButton(text="📰 News / 新闻", callback_data="menu_stub|news"),
            InlineKeyboardButton(text="❌ Cancel Booking / 取消预约", callback_data="menu_stub|cancel_booking"),
        ]
    ])

    # Отправляем новое меню
    try:
        sent_msg = await message.answer_photo(
            photo=MENU_PHOTO_ID,
            caption="Главное меню",
            reply_markup=kb
        )
        # Запоминаем ID этого сообщения
        last_menu_message[chat_id] = sent_msg.message_id
    except Exception as e:
        logging.error(f"Не удалось отправить меню в чате {chat_id}: {e}")


@menu_router.callback_query(F.data.startswith("menu_stub|"))
async def on_menu_stub(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатия на любые кнопки из /menu (префикс menu_stub|...).
    Если нажата кнопка "booking", то редактируем сообщение,
    отображаем картинку и клавиатуру выбора группы (как в /book),
    и переводим пользователя в состояние BookUserStates.waiting_for_group.
    Остальные пока заглушки.
    """
    parts = callback.data.split("|")
    if len(parts) != 2:
        return await callback.answer("Некорректные данные!", show_alert=True)

    action = parts[1]

    # Если нажали "booking" — запускаем логику
    if action == "booking":
        # Формируем такую же клавиатуру выбора групп, как в /book
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
            # Пытаемся отредактировать старое сообщение (меняем фото + подпись + кнопки)
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=BOOKING_PHOTO_ID,
                    caption="Выберите группу для бронирования:"
                ),
                reply_markup=kb
            )
        except TelegramBadRequest as e:
            # Если сообщение изначально было текстом, редактирование media не сработает
            logging.warning(f"Edit media failed: {e}. Удаляем и шлём новое.")
            # Удаляем старое и отправляем новое
            try:
                await callback.message.delete()
            except:
                pass
            new_msg = await callback.message.answer_photo(
                photo=BOOKING_PHOTO_ID,
                caption="Выберите группу для бронирования:",
                reply_markup=kb
            )
            # При желании можно сохранить new_msg.message_id вместо старого,
            # если вы хотите далее удалять именно его.

        # Устанавливаем FSM: ждём выбор группы
        await state.set_state(BookUserStates.waiting_for_group)

        # Уведомим пользователя, что ок
        await callback.answer()
        return

    # Иначе — заглушки
    if action == "girls":
        await callback.answer("Заглушка: список Girls...", show_alert=True)
    elif action == "news":
        try:
            # Пытаемся отредактировать старое сообщение,
            # меняем фото и подпись (например, "Последние новости").
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=MENU_PHOTO_ID,  # Можно NEWS_PHOTO_ID, если есть отдельная картинка
                    caption="Последние новости:"
                ),
                reply_markup=None  # Можно убрать кнопки или сделать свою клавиатуру
            )
        except TelegramBadRequest as e:
            # Если старое сообщение было не фото/медиа, edit_media не сработает
            logging.warning(f"Edit media failed: {e}. Удаляем старое и шлём новое.")
            try:
                await callback.message.delete()
            except:
                pass
            # Отправляем новое
            await callback.message.answer_photo(
                photo=MENU_PHOTO_ID,
                caption="Последние новости:"
            )

        # Теперь вызываем вашу команду /news (или напрямую show_news)
        # Вместо callback.message можно передать "фиктивное" Message,
        # но проще просто вызвать cmd_show_news и передать "callback.message"
        await cmd_show_news(callback.message)

        # Закрываем alert
        await callback.answer()
    elif action == "balance":
        await callback.answer("Заглушка: показ баланса...", show_alert=True)
    elif action == "all_booking":
        await callback.answer("Заглушка: все бронирования...", show_alert=True)
    elif action == "cancel_booking":
        await callback.answer("Заглушка: отмена бронирования...", show_alert=True)
    else:
        await callback.answer("Неизвестная команда меню!", show_alert=True)