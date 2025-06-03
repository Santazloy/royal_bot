import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext

from utils.bot_utils import safe_answer
from constants.booking_const import GROUP_CHOICE_IMG, groups_data
from handlers.states import BookUserStates
from handlers.language import get_user_language, get_message
from handlers.booking.cancelbook import cmd_off  # ← универсальный /off

menu_router = Router()

MENU_PHOTO_ID = "photo/IMG_2585.JPG"


# ─────────────────────────── /menu ────────────────────────────────────────────
@menu_router.message(Command("menu"))
async def cmd_menu(message: Message):
    lang = await get_user_language(message.from_user.id)
    try:
        await safe_answer(
            message,
            photo=MENU_PHOTO_ID,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message(lang, "menu_btn_booking"),
                        callback_data="menu_stub|booking"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_message(lang, "menu_btn_schedule"),
                        callback_data="view_all_bookings"
                    ),
                    InlineKeyboardButton(
                        text=get_message(lang, "menu_btn_balance"),
                        callback_data="menu_stub|balance"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_message(lang, "menu_btn_cancel_booking"),
                        callback_data="menu_stub|cancel_booking"
                    )
                ],
            ])
        )
    except Exception as e:
        logging.error("Не удалось отправить меню: %s", e)


# ───────────────────   меню → «Бронирование»   ───────────────────────────────
@menu_router.callback_query(F.data == "menu_stub|booking")
async def on_menu_stub_booking(cb: CallbackQuery, state: FSMContext):
    # Игнорируем колбэки от самого бота
    me = await cb.bot.get_me()
    if cb.from_user.id == me.id:
        return

    lang = await get_user_language(cb.from_user.id)

    rows, buf = [], []
    for i, gk in enumerate(groups_data, 1):
        buf.append(
            InlineKeyboardButton(text=gk, callback_data=f"bkgrp_{gk}")
        )
        if i % 3 == 0:
            rows.append(buf)
            buf = []
    if buf:
        rows.append(buf)

    try:
        await cb.message.delete()
    except Exception:
        pass

    await safe_answer(
        cb,
        photo=GROUP_CHOICE_IMG,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await state.set_state(BookUserStates.waiting_for_group)


# ───────────────────   меню → «Баланс» (заглушка)  ────────────────────────────
@menu_router.callback_query(F.data == "menu_stub|balance")
async def on_menu_stub_balance(cb: CallbackQuery, state: FSMContext):
    # Игнорируем колбэки от самого бота
    me = await cb.bot.get_me()
    if cb.from_user.id == me.id:
        return

    lang = await get_user_language(cb.from_user.id)
    await safe_answer(
        cb,
        photo=MENU_PHOTO_ID,
        caption=get_message(lang, "menu_no_action")
    )


# ───────────────────   меню → «Отмена бронирования»  ──────────────────────────
@menu_router.callback_query(F.data == "menu_stub|cancel_booking")
async def on_menu_stub_cancel_booking(cb: CallbackQuery, state: FSMContext):
    """
    По нажатию «Отмена бронирования» вызываем тот же сценарий,
    что и команда /off, но через CallbackQuery.
    """
    # Игнорируем колбэки от самого бота
    me = await cb.bot.get_me()
    if cb.from_user.id == me.id:
        return

    try:
        await cb.message.delete()
    except Exception:
        pass

    await cb.answer()          # убираем «часики» на кнопке
    await cmd_off(cb)          # ← универсальный вызов /off


# ─────────────────────────   обработка ненайденных menu_stub  ─────────────────────────
@menu_router.callback_query(F.data.startswith("menu_stub|"))
async def on_menu_stub_unknown(cb: CallbackQuery, state: FSMContext):
    # Игнорируем колбэки от самого бота
    me = await cb.bot.get_me()
    if cb.from_user.id == me.id:
        return

    lang = await get_user_language(cb.from_user.id)
    await safe_answer(
        cb,
        photo=MENU_PHOTO_ID,
        caption=get_message(lang, "menu_unknown")
    )
