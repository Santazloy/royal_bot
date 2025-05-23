# handlers/booking/router.py

import logging
import html
from aiogram import Bot, Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from constants.booking_const import (
    BOOKING_REPORT_GROUP_ID, SPECIAL_USER_ID, FINANCIAL_REPORT_GROUP_ID,
    GROUP_CHOICE_IMG, DAY_CHOICE_IMG, TIME_CHOICE_IMG, FINAL_BOOKED_IMG,
    special_payments, status_mapping, distribution_variants, groups_data
)
from constants.salary import salary_options
from utils.user_utils import get_user_language
from utils.text_utils import get_message, format_html_pre
from utils.time_utils import (
    generate_daily_time_slots as generate_time_slots,
    get_adjacent_time_slots, get_slot_datetime_shanghai
)

# **правильный** импорт BookingRepo и дата-менеджера
from db_access.booking_repo import BookingRepo
from handlers.booking.data_manager import BookingDataManager

from app_states import BookUserStates, BookPaymentStates

logger = logging.getLogger(__name__)
router = Router()

repo = BookingRepo(db.db_pool)
data_mgr = BookingDataManager(groups_data)


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext):
    await state.clear()
    keys = data_mgr.list_group_keys()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=k, callback_data=f"bkgrp_{k}") for k in keys[i:i+3]]
            for i in range(0, len(keys), 3)
        ]
    )
    await message.answer_photo(photo=GROUP_CHOICE_IMG, caption="", reply_markup=kb)
    await state.set_state(BookUserStates.waiting_for_group)


@router.callback_query(StateFilter(BookUserStates.waiting_for_group), F.data.startswith("bkgrp_"))
async def user_select_group(cb: CallbackQuery, state: FSMContext):
    gk = cb.data.removeprefix("bkgrp_")
    if gk not in groups_data:
        return await cb.answer("Нет такой группы!", show_alert=True)
    await state.update_data(selected_group=gk)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="bkday_Сегодня"),
                InlineKeyboardButton(text="Завтра", callback_data="bkday_Завтра"),
            ]
        ]
    )
    try:
        await cb.message.edit_media(
            media=InputMediaPhoto(media=DAY_CHOICE_IMG, caption=""), reply_markup=kb
        )
    except TelegramBadRequest:
        await cb.message.answer_photo(photo=DAY_CHOICE_IMG, caption="", reply_markup=kb)

    await cb.answer()
    await state.set_state(BookUserStates.waiting_for_day)


@router.callback_query(StateFilter(BookUserStates.waiting_for_day), F.data.startswith("bkday_"))
async def user_select_day(cb: CallbackQuery, state: FSMContext):
    day = cb.data.removeprefix("bkday_")
    await state.update_data(selected_day=day)
    await send_time_slots(cb, day, state)

# делаем так:
async def send_time_slots(
    callback_query: CallbackQuery,
    selected_day: str,
    state: FSMContext
):
    """
    Показываем пользователю свободные слоты + кнопку «Назад» к выбору дня.
    """
    data = await state.get_data()
    gk = data["selected_group"]
    ginfo = groups_data[gk]

    # 1) Собираем занятые и недоступные слоты
    busy = set(ginfo["booked_slots"].get(selected_day, []))
    for bs in list(busy):
        busy.update(get_adjacent_time_slots(bs))
    busy |= ginfo["unavailable_slots"].get(selected_day, set())

    # 2) Блокируем любые финальные статусы
    final = {'❌❌❌', '✅', '✅2', '✅✅', '✅✅✅'}
    for (d, t), st in ginfo["time_slot_statuses"].items():
        if d == selected_day and st in final:
            busy.add(t)

    # 3) Строим клавиатуру из свободных слотов
    builder = InlineKeyboardBuilder()
    for slot in generate_time_slots():
        if slot not in busy:
            builder.button(text=slot, callback_data=f"bkslot_{slot.replace(':','_')}")
    # Кнопка «Назад»
    builder.button(text="« Назад", callback_data="bkday_back")
    builder.adjust(4)
    kb = builder.as_markup()

    # 4) Подпись
    lang = await get_user_language(callback_query.from_user.id)
    day_label = get_message(lang, 'today') if selected_day == 'Сегодня' else get_message(lang, 'tomorrow')
    text = get_message(lang, 'choose_time_styled', day=day_label)
    caption = format_html_pre(text)

    # 5) Редактируем или шлём новое медиа
    try:
        await callback_query.message.edit_media(
            media=InputMediaPhoto(media=TIME_CHOICE_IMG, caption=caption),
            reply_markup=kb
        )
    except TelegramBadRequest:
        await callback_query.message.answer_photo(
            photo=TIME_CHOICE_IMG, caption=caption, reply_markup=kb
        )

    await callback_query.answer()
    await state.set_state(BookUserStates.waiting_for_time)

@router.callback_query(StateFilter(BookUserStates.waiting_for_time), F.data.startswith("bkslot_"))
async def user_select_time(cb: CallbackQuery, state: FSMContext):
    slot = cb.data.removeprefix("bkslot_").replace("_", ":")
    data = await state.get_data()
    gk, day, uid = data["selected_group"], data["selected_day"], cb.from_user.id

    # Заполняем структуры в памяти
    data_mgr.book_slot(gk, day, slot, uid)
    # Запись в БД: создаём booking
    iso = get_slot_datetime_shanghai(day, slot)
    await repo.add_booking(gk, day, slot, uid, iso)

    # Отправим уведомление в спец. группу
    await send_booking_report(cb.bot, uid, gk, slot, day)
    await state.clear()

    # Сообщаем пользователю
    lang = await get_user_language(uid)
    txt = get_message(lang, 'slot_booked', time=slot, day=day, group=gk)
    caption = format_html_pre(txt)
    try:
        await cb.message.edit_media(
            media=InputMediaPhoto(media=FINAL_BOOKED_IMG, caption=caption),
            reply_markup=None,
        )
    except TelegramBadRequest:
        await cb.message.answer_photo(photo=FINAL_BOOKED_IMG, caption=caption)

    await cb.answer()
    # Обновляем сообщение в группе, чтобы появилась кнопка с booked
    await update_group_message(cb.bot, gk)


async def send_booking_report(bot: Bot, uid: int, gk: str, slot: str, day: str):
    username = f"User {uid}"
    user_emoji = "❓"
    if db.db_pool:
        try:
            async with db.db_pool.acquire() as con:
                row = await con.fetchrow(
                    "SELECT u.username, e.emoji "
                    "FROM users u LEFT JOIN user_emojis e ON u.user_id=e.user_id "
                    "WHERE u.user_id=$1",
                    uid,
                )
                if row:
                    username = row["username"] or username
                    user_emoji = (row["emoji"] or "").split(",")[0] or user_emoji
        except Exception as e:
            logger.error(e)

    body = (
        f"📅 Новый Booking\n"
        f"👤 Пользователь: {user_emoji} {html.escape(username)}\n"
        f"🌹 Группа: {gk}\n"
        f"⏰ Время: {slot} ({day})"
    )
    await bot.send_message(
        chat_id=BOOKING_REPORT_GROUP_ID,
        text=f"<pre>{body}</pre>",
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("group_time|"))
async def admin_click_slot(cb: CallbackQuery):
    """
    Админ нажал на кнопку «<день> <время>» в групчатике — показываем
    варианты финального статуса + крестик Отменить + «Назад».
    """
    _, gk, day, slot = cb.data.split("|")
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer("Нет прав!", show_alert=True)

    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer("Только админ!", show_alert=True)

    # Строим клавиатуру:
    # — первая строка: ✅, ✅2, ✅✅, ✅✅✅
    # — вторая: ❌❌❌ (отменить)
    # — третья: « Назад»
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=emoji,
                callback_data=f"group_status|{gk}|{day}|{slot}|{code}"
            )
            for code, emoji in status_mapping.items()
        ],
        [
            InlineKeyboardButton(
                text="❌❌❌ Отменить",
                callback_data=f"group_status|{gk}|{day}|{slot}|-1"
            )
        ],
        [
            InlineKeyboardButton(
                text="« Назад",
                callback_data=f"group_status|{gk}|{day}|{slot}|back"
            )
        ]
    ])

    await cb.message.edit_text(
        "<b>Выберите финальный статус слота:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    await cb.answer()

@router.callback_query(F.data.startswith("group_status|"))
async def admin_click_status(cb: CallbackQuery):
    """
    Завершение (или отмена) бронирования админом.
    Если выбран ❌❌❌, то запись и слоты удаляются, всё возвращается в список.
    Если выбран другой статус, то слот становится финальным, кнопка пропадает.
    """
    parts = cb.data.split("|")
    _, gk, day, slot, code = parts
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer("Нет прав!", show_alert=True)

    # Проверяем, что нажал админ
    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer("Нет прав!", show_alert=True)

    # Кнопка "Назад" -> просто обновляем сообщение
    if code == "back":
        await update_group_message(cb.bot, gk)
        return await cb.answer()

    # [!!! CHANGE] Если выбрана ❌❌❌ — отменяем бронирование, всё чистим
    if code == "-1":
        # Удаляем слот из памяти
        uid = ginfo["slot_bookers"].pop((day, slot), None)
        if uid and slot in ginfo["booked_slots"].get(day, []):
            ginfo["booked_slots"][day].remove(slot)

        # Возвращаем соседние слоты из unavailable, если они принадлежали этому же юзеру
        adjs = get_adjacent_time_slots(slot)
        for adj in adjs:
            if adj in ginfo["unavailable_slots"][day]:
                ginfo["unavailable_slots"][day].remove(adj)
                # Удаляем статус, если он там был
                if (day, adj) in ginfo["time_slot_statuses"]:
                    del ginfo["time_slot_statuses"][(day, adj)]
                # Удаляем booker, если это тот же пользователь
                if (day, adj) in ginfo["slot_bookers"]:
                    if ginfo["slot_bookers"][(day, adj)] == uid:
                        ginfo["slot_bookers"].pop((day, adj), None)

        # Удаляем основной слот из статусов
        if (day, slot) in ginfo["time_slot_statuses"]:
            del ginfo["time_slot_statuses"][(day, slot)]

        # Удаляем из БД
        try:
            if db.db_pool:
                async with db.db_pool.acquire() as con:
                    await con.execute(
                        "DELETE FROM bookings "
                        "WHERE group_key=$1 AND day=$2 AND time_slot=$3",
                        gk, day, slot
                    )# handlers/booking/router.py

import logging
import html
from aiogram import Bot, Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from constants.booking_const import (
    BOOKING_REPORT_GROUP_ID, SPECIAL_USER_ID, FINANCIAL_REPORT_GROUP_ID,
    GROUP_CHOICE_IMG, DAY_CHOICE_IMG, TIME_CHOICE_IMG, FINAL_BOOKED_IMG,
    special_payments, status_mapping, distribution_variants, groups_data
)
from constants.salary import salary_options
from utils.user_utils import get_user_language
from utils.text_utils import get_message, format_html_pre
from utils.time_utils import (
    generate_daily_time_slots as generate_time_slots,
    get_adjacent_time_slots, get_slot_datetime_shanghai
)

# **правильный** импорт BookingRepo и дата-менеджера
from db_access.booking_repo import BookingRepo
from handlers.booking.data_manager import BookingDataManager

from app_states import BookUserStates, BookPaymentStates

logger = logging.getLogger(__name__)
router = Router()

repo = BookingRepo(db.db_pool)
data_mgr = BookingDataManager(groups_data)


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext):
    await state.clear()
    keys = data_mgr.list_group_keys()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=k, callback_data=f"bkgrp_{k}") for k in keys[i:i+3]]
            for i in range(0, len(keys), 3)
        ]
    )
    await message.answer_photo(photo=GROUP_CHOICE_IMG, caption="", reply_markup=kb)
    await state.set_state(BookUserStates.waiting_for_group)


@router.callback_query(StateFilter(BookUserStates.waiting_for_group), F.data.startswith("bkgrp_"))
async def user_select_group(cb: CallbackQuery, state: FSMContext):
    gk = cb.data.removeprefix("bkgrp_")
    if gk not in groups_data:
        return await cb.answer("Нет такой группы!", show_alert=True)
    await state.update_data(selected_group=gk)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="bkday_Сегодня"),
                InlineKeyboardButton(text="Завтра", callback_data="bkday_Завтра"),
            ]
        ]
    )
    try:
        await cb.message.edit_media(
            media=InputMediaPhoto(media=DAY_CHOICE_IMG, caption=""), reply_markup=kb
        )
    except TelegramBadRequest:
        await cb.message.answer_photo(photo=DAY_CHOICE_IMG, caption="", reply_markup=kb)

    await cb.answer()
    await state.set_state(BookUserStates.waiting_for_day)


@router.callback_query(StateFilter(BookUserStates.waiting_for_day), F.data.startswith("bkday_"))
async def user_select_day(cb: CallbackQuery, state: FSMContext):
    day = cb.data.removeprefix("bkday_")
    await state.update_data(selected_day=day)
    await send_time_slots(cb, day, state)

# делаем так:
async def send_time_slots(
    callback_query: CallbackQuery,
    selected_day: str,
    state: FSMContext
):
    """
    Показываем пользователю свободные слоты + кнопку «Назад» к выбору дня.
    """
    data = await state.get_data()
    gk = data["selected_group"]
    ginfo = groups_data[gk]

    # 1) Собираем занятые и недоступные слоты
    busy = set(ginfo["booked_slots"].get(selected_day, []))
    for bs in list(busy):
        busy.update(get_adjacent_time_slots(bs))
    busy |= ginfo["unavailable_slots"].get(selected_day, set())

    # 2) Блокируем любые финальные статусы
    final = {'❌❌❌', '✅', '✅2', '✅✅', '✅✅✅'}
    for (d, t), st in ginfo["time_slot_statuses"].items():
        if d == selected_day and st in final:
            busy.add(t)

    # 3) Строим клавиатуру из свободных слотов
    builder = InlineKeyboardBuilder()
    for slot in generate_time_slots():
        if slot not in busy:
            builder.button(text=slot, callback_data=f"bkslot_{slot.replace(':','_')}")
    # Кнопка «Назад»
    builder.button(text="« Назад", callback_data="bkday_back")
    builder.adjust(4)
    kb = builder.as_markup()

    # 4) Подпись
    lang = await get_user_language(callback_query.from_user.id)
    day_label = get_message(lang, 'today') if selected_day == 'Сегодня' else get_message(lang, 'tomorrow')
    text = get_message(lang, 'choose_time_styled', day=day_label)
    caption = format_html_pre(text)

    # 5) Редактируем или шлём новое медиа
    try:
        await callback_query.message.edit_media(
            media=InputMediaPhoto(media=TIME_CHOICE_IMG, caption=caption),
            reply_markup=kb
        )
    except TelegramBadRequest:
        await callback_query.message.answer_photo(
            photo=TIME_CHOICE_IMG, caption=caption, reply_markup=kb
        )

    await callback_query.answer()
    await state.set_state(BookUserStates.waiting_for_time)

@router.callback_query(StateFilter(BookUserStates.waiting_for_time), F.data.startswith("bkslot_"))
async def user_select_time(cb: CallbackQuery, state: FSMContext):
    slot = cb.data.removeprefix("bkslot_").replace("_", ":")
    data = await state.get_data()
    gk, day, uid = data["selected_group"], data["selected_day"], cb.from_user.id

    # Заполняем структуры в памяти
    data_mgr.book_slot(gk, day, slot, uid)
    # Запись в БД: создаём booking
    iso = get_slot_datetime_shanghai(day, slot)
    await repo.add_booking(gk, day, slot, uid, iso)

    # Отправим уведомление в спец. группу
    await send_booking_report(cb.bot, uid, gk, slot, day)
    await state.clear()

    # Сообщаем пользователю
    lang = await get_user_language(uid)
    txt = get_message(lang, 'slot_booked', time=slot, day=day, group=gk)
    caption = format_html_pre(txt)
    try:
        await cb.message.edit_media(
            media=InputMediaPhoto(media=FINAL_BOOKED_IMG, caption=caption),
            reply_markup=None,
        )
    except TelegramBadRequest:
        await cb.message.answer_photo(photo=FINAL_BOOKED_IMG, caption=caption)

    await cb.answer()
    # Обновляем сообщение в группе, чтобы появилась кнопка с booked
    await update_group_message(cb.bot, gk)


async def send_booking_report(bot: Bot, uid: int, gk: str, slot: str, day: str):
    username = f"User {uid}"
    user_emoji = "❓"
    if db.db_pool:
        try:
            async with db.db_pool.acquire() as con:
                row = await con.fetchrow(
                    "SELECT u.username, e.emoji "
                    "FROM users u LEFT JOIN user_emojis e ON u.user_id=e.user_id "
                    "WHERE u.user_id=$1",
                    uid,
                )
                if row:
                    username = row["username"] or username
                    user_emoji = (row["emoji"] or "").split(",")[0] or user_emoji
        except Exception as e:
            logger.error(e)

    body = (
        f"📅 Новый Booking\n"
        f"👤 Пользователь: {user_emoji} {html.escape(username)}\n"
        f"🌹 Группа: {gk}\n"
        f"⏰ Время: {slot} ({day})"
    )
    await bot.send_message(
        chat_id=BOOKING_REPORT_GROUP_ID,
        text=f"<pre>{body}</pre>",
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("group_time|"))
async def admin_click_slot(cb: CallbackQuery):
    """
    Админ нажал на кнопку «<день> <время>» в групчатике — показываем
    варианты финального статуса + крестик Отменить + «Назад».
    """
    _, gk, day, slot = cb.data.split("|")
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer("Нет прав!", show_alert=True)

    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer("Только админ!", show_alert=True)

    # Строим клавиатуру:
    # — первая строка: ✅, ✅2, ✅✅, ✅✅✅
    # — вторая: ❌❌❌ (отменить)
    # — третья: « Назад»
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=emoji,
                callback_data=f"group_status|{gk}|{day}|{slot}|{code}"
            )
            for code, emoji in status_mapping.items()
        ],
        [
            InlineKeyboardButton(
                text="❌❌❌ Отменить",
                callback_data=f"group_status|{gk}|{day}|{slot}|-1"
            )
        ],
        [
            InlineKeyboardButton(
                text="« Назад",
                callback_data=f"group_status|{gk}|{day}|{slot}|back"
            )
        ]
    ])

    await cb.message.edit_text(
        "<b>Выберите финальный статус слота:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    await cb.answer()

@router.callback_query(F.data.startswith("group_status|"))
async def admin_click_status(cb: CallbackQuery):
    """
    Завершение (или отмена) бронирования админом.
    Если выбран ❌❌❌, то запись и слоты удаляются, всё возвращается в список.
    Если выбран другой статус, то слот становится финальным, кнопка пропадает.
    """
    parts = cb.data.split("|")
    _, gk, day, slot, code = parts
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer("Нет прав!", show_alert=True)

    # Проверяем, что нажал админ
    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer("Нет прав!", show_alert=True)

    # Кнопка "Назад" -> просто обновляем сообщение
    if code == "back":
        await update_group_message(cb.bot, gk)
        return await cb.answer()

    # [!!! CHANGE] Если выбрана ❌❌❌ — отменяем бронирование, всё чистим
    if code == "-1":
        # Удаляем слот из памяти
        uid = ginfo["slot_bookers"].pop((day, slot), None)
        if uid and slot in ginfo["booked_slots"].get(day, []):
            ginfo["booked_slots"][day].remove(slot)

        # Возвращаем соседние слоты из unavailable, если они принадлежали этому же юзеру
        adjs = get_adjacent_time_slots(slot)
        for adj in adjs:
            if adj in ginfo["unavailable_slots"][day]:
                ginfo["unavailable_slots"][day].remove(adj)
                # Удаляем статус, если он там был
                if (day, adj) in ginfo["time_slot_statuses"]:
                    del ginfo["time_slot_statuses"][(day, adj)]
                # Удаляем booker, если это тот же пользователь
                if (day, adj) in ginfo["slot_bookers"]:
                    if ginfo["slot_bookers"][(day, adj)] == uid:
                        ginfo["slot_bookers"].pop((day, adj), None)

        # Удаляем основной слот из статусов
        if (day, slot) in ginfo["time_slot_statuses"]:
            del ginfo["time_slot_statuses"][(day, slot)]

        # Удаляем из БД
        try:
            if db.db_pool:
                async with db.db_pool.acquire() as con:
                    await con.execute(
                        "DELETE FROM bookings "
                        "WHERE group_key=$1 AND day=$2 AND time_slot=$3",
                        gk, day, slot
                    )
                    await con.execute(
                        "DELETE FROM group_time_slot_statuses "
                        "WHERE group_key=$1 AND day=$2 AND time_slot=$3",
                        gk, day, slot
                    )
        except Exception as e:
            logger.error(f"DB error on delete: {e}")

        # Обновляем сообщение
        await update_group_message(cb.bot, gk)
        return await cb.answer("Слот отменён.")

    # Иначе устанавливаем финальный статус (✅, ✅2 и т.д.)
    emoji = status_mapping.get(code)
    ginfo["time_slot_statuses"][(day, slot)] = emoji

    # Запоминаем в БД (status и status_code)
    uid = ginfo["slot_bookers"].get((day, slot))
    if db.db_pool:
        try:
            async with db.db_pool.acquire() as con:
                await con.execute(
                    "UPDATE bookings SET status_code=$1, status=$2 "
                    "WHERE group_key=$3 AND day=$4 AND time_slot=$5",
                    code, emoji, gk, day, slot
                )
                # Обновляем (или вставляем) статусы
                await con.execute(
                    """
                    INSERT INTO group_time_slot_statuses
                      (group_key, day, time_slot, status, user_id)
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT (group_key, day, time_slot)
                    DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                    """,
                    gk, day, slot, emoji, uid
                )
        except Exception as e:
            logger.error(f"DB error: {e}")

    # Применим, если нужно, награду для SPECIAL_USER_ID
    await apply_special_user_reward(code, cb.bot)

    # После выбора статуса предлагаем выбрать способ оплаты (cash/beznal/agent)
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Наличные", callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|cash"),
        InlineKeyboardButton(text="Безнал",   callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|beznal"),
        InlineKeyboardButton(text="Агент",    callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|agent"),
    ]])
    await cb.message.edit_text("Выберите способ оплаты:", parse_mode=ParseMode.HTML, reply_markup=pay_kb)
    await cb.answer()


async def apply_special_user_reward(status_code: str, bot: Bot):
    amount = special_payments.get(status_code, 0)
    if amount <= 0 or not db.db_pool:
        return
    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", SPECIAL_USER_ID)
        if row:
            new = row["balance"] + amount
            await conn.execute("UPDATE users SET balance=$1 WHERE user_id=$2", new, SPECIAL_USER_ID)
        else:
            new = amount
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                SPECIAL_USER_ID, "Special User", amount
            )
    finally:
        await db.db_pool.release(conn)
    try:
        await bot.send_message(SPECIAL_USER_ID, f"Вам начислено дополнительно {amount}¥.\nТекущий баланс: {new}¥")
    except:
        pass


@router.callback_query(F.data.startswith("payment_method|"))
async def process_payment_method(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split("|")
    _, gk, day, slot, code, method = parts
    lang = await get_user_language(cb.from_user.id)
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer(get_message(lang, "no_permission"), show_alert=True)

    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer(get_message(lang, "no_permission"), show_alert=True)

    if not db.db_pool:
        return await cb.answer("Нет подключения к БД", show_alert=True)

    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot,
        )
    finally:
        await db.db_pool.release(conn)
    if not row:
        return await cb.answer(get_message(lang, "no_such_booking"), show_alert=True)

    await cb.answer()
    if method in ("cash", "beznal"):
        txt = get_message(lang, "enter_payment_amount")
        await state.update_data(
            group_key=gk, day=day, time_slot=slot, status_code=code, payment_method=method
        )
        try:
            await cb.bot.edit_message_text(
                chat_id=cb.message.chat.id,
                message_id=cb.message.message_id,
                text=format_html_pre(txt),
                parse_mode=ParseMode.HTML,
            )
        except TelegramBadRequest:
            pass
        await state.set_state(BookPaymentStates.waiting_for_amount)
    else:
        # Агент
        await handle_agent_payment(cb, gk, day, slot, code)


async def handle_agent_payment(cb: CallbackQuery, gk: str, day: str, slot: str, status_code: str):
    """
    При 'Агент' своя логика расчётов, если требуется.
    """
    bot = cb.bot
    uid = cb.from_user.id
    lang = await get_user_language(uid)
    emoji = status_mapping.get(status_code)
    if not emoji:
        return await cb.answer("Некорректный статус!", show_alert=True)
    ginfo = groups_data.get(gk)
    if not ginfo:
        return await cb.answer("Нет такой группы!", show_alert=True)

    # Ниже упрощённая логика, у вас может быть своя
    base = salary_options[ginfo["salary_option"]].get(emoji, 0)
    deduct_map = {"0": 1500, "1": 2100, "2": 3000, "3": 4500}
    deduct = deduct_map.get(status_code, 0)

    ginfo["salary"] += base
    conn = await db.db_pool.acquire()
    try:
        await conn.execute("UPDATE group_financial_data SET salary=$1 WHERE group_key=$2", ginfo["salary"], gk)
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot,
        )
        if not row:
            return await cb.answer(get_message(lang, "no_such_booking"), show_alert=True)
        booked = row["user_id"]
        await update_user_financial_info(booked, -deduct, bot)
        bal_row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", booked)
        bal = bal_row["balance"] if bal_row else 0
        msg = get_message(lang, "changed_balance_user", op="-", amount=deduct, balance=bal)
        await bot.send_message(booked, format_html_pre(msg), parse_mode=ParseMode.HTML)
    finally:
        await db.db_pool.release(conn)

    # Обновляем сообщение в группе
    try:
        await update_group_message(bot, gk)
    except TelegramBadRequest:
        pass

    await send_financial_report(bot)
    await cb.answer("Оплата (agent) учтена.")


async def update_user_financial_info(user_id: int, net_amount: int, bot: Bot):
    """
    Прибавляем (или вычитаем, если net_amount < 0) net_amount к балансу и профиту user_id
    """
    if not db.db_pool:
        return
    try:
        member = await bot.get_chat_member(user_id, user_id)
        uname = member.user.username or f"{member.user.first_name} {member.user.last_name}"
    except:
        uname = f"User_{user_id}"
    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow(
            "SELECT balance, profit, monthly_profit FROM users WHERE user_id=$1", user_id
        )
        if row:
            b, p, m = row["balance"], row["profit"], row["monthly_profit"]
            nb, np, nm = b + net_amount, p + net_amount, m + net_amount
            await conn.execute(
                "UPDATE users SET balance=$1, profit=$2, monthly_profit=$3, username=$4 WHERE user_id=$5",
                nb, np, nm, uname, user_id
            )
        else:
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                user_id, uname, net_amount
            )
    finally:
        await db.db_pool.release(conn)


async def apply_additional_payment(user_id: int, status_code: str, bot: Bot):
    """
    Если нужно доплачивать особому пользователю (SPECIAL_USER_ID), не путать с apply_special_user_reward().
    Можно объединить, если логика дублируется.
    """
    if user_id != SPECIAL_USER_ID:
        return
    extra = special_payments.get(status_code, 0)
    if extra <= 0:
        return
    if not db.db_pool:
        return

    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", user_id)
        if row:
            newb = row["balance"] + extra
            await conn.execute("UPDATE users SET balance=$1 WHERE user_id=$2", newb, user_id)
            await bot.send_message(
                user_id,
                f"<pre>Вам начислено дополнительно {extra}¥.\nВаш текущий баланс: {newb}¥</pre>",
                parse_mode=ParseMode.HTML,
            )
        else:
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                user_id, "Special User", extra
            )
            await bot.send_message(
                user_id,
                f"<pre>Вам начислено дополнительно {extra}¥.\nВаш текущий баланс: {extra}¥</pre>",
                parse_mode=ParseMode.HTML,
            )
    finally:
        await db.db_pool.release(conn)


@router.message(StateFilter(BookPaymentStates.waiting_for_amount), F.text)
async def process_payment_amount(message: Message, state: FSMContext):
    """
    Обработка цифры, введённой админом (сумма оплаты).
    """
    user = message.from_user
    lang = await get_user_language(user.id)
    data = await state.get_data()
    gk, day, slot = data["group_key"], data["day"], data["time_slot"]
    code, method = data["status_code"], data["payment_method"]

    try:
        amt = int(message.text.strip())
    except ValueError:
        return await message.reply(format_html_pre(get_message(lang, "incorrect_input")),
                                   parse_mode=ParseMode.HTML)

    emoji = status_mapping.get(str(code))
    if not emoji:
        await state.clear()
        return await message.reply(get_message(lang, "invalid_data"))

    if not db.db_pool:
        await state.clear()
        return await message.reply("Нет соединения с БД.")

    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot,
        )
        if not row:
            await state.clear()
            return await message.reply(get_message(lang, "no_such_booking"))
        booked = row["user_id"]

        await conn.execute(
            "UPDATE bookings SET payment_method=$1, amount=$2 "
            "WHERE group_key=$3 AND day=$4 AND time_slot=$5 AND user_id=$6",
            method, amt, gk, day, slot, booked,
        )

        base = salary_options[groups_data[gk]["salary_option"]].get(emoji, 0)
        deduct_map = {"0": 1500, "1": 2100, "2": 3000, "3": 4500}
        deduct = deduct_map.get(str(code), 0)

        groups_data[gk]["salary"] += base
        await conn.execute("UPDATE group_financial_data SET salary=$1 WHERE group_key=$2",
                           groups_data[gk]["salary"], gk)

        if method == "cash":
            groups_data[gk]["cash"] += amt
            await conn.execute("UPDATE group_financial_data SET cash=$1 WHERE group_key=$2",
                               groups_data[gk]["cash"], gk)

        net = amt - deduct
        await update_user_financial_info(booked, net, message.bot)
        await apply_additional_payment(booked, str(code), message.bot)

        # Если есть distribution_variant, начисляем целевому пользователю
        var = groups_data[gk].get("distribution_variant")
        dist_data = distribution_variants.get(var, distribution_variants["variant_400"])
        dist_amt = dist_data.get(str(code), 0)
        tgt = groups_data[gk].get("target_id")
        if dist_amt > 0 and tgt:
            await update_user_financial_info(tgt, dist_amt, message.bot)
    finally:
        await db.db_pool.release(conn)

    try:
        await update_group_message(message.bot, gk)
    except TelegramBadRequest:
        pass

    await send_financial_report(message.bot)
    await state.clear()
    await message.answer(f"Учли оплату {amt} (метод={method}), статус={emoji}.")


async def update_group_message(bot: Bot, group_key: str):
    """
    Перерисовывает сообщение в группе (chat_id, message_id),
    показывая актуальные статусы слотов и кнопки для тех, что ещё в состоянии 'booked'.
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from utils.text_utils import format_html_pre

    ginfo = groups_data[group_key]
    chat_id = ginfo["chat_id"]
    user_lang = "ru"  # при желании можно хранить язык для группы отдельно

    # 1) Формируем текст (шапка, финансы и т.д.)
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"━━━━━━  🌹🌹 {group_key} 🌹🌹  ━━━━━━",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{get_message(user_lang,'salary')}: {ginfo.get('salary',0)}¥",
        f"{get_message(user_lang,'cash')}:   {ginfo.get('cash',0)}¥",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {get_message(user_lang,'booking_report')} ⏰",
    ]

    # Для отображения финальных статусов нам нужно знать эмодзи юзеров
    async def get_user_emoji(uid: int) -> str:
        if not uid or not db.db_pool:
            return "❓"
        try:
            async with db.db_pool.acquire() as con:
                row = await con.fetchrow("SELECT emoji FROM user_emojis WHERE user_id=$1", uid)
                if row and row["emoji"]:
                    return row["emoji"].split(",")[0]
        except:
            pass
        return "❓"

    # 2) Генерируем блоки для Сегодня/Завтра
    final_statuses = {'❌❌❌','✅','✅2','✅✅','✅✅✅'}
    for day in ("Сегодня", "Завтра"):
        lines.append(f"\n{day}:")
        for slot in generate_time_slots():
            st = ginfo["time_slot_statuses"].get((day, slot))
            if st and st in final_statuses:
                # Слот уже имеет окончательный статус -> показываем в тексте
                uid = ginfo["slot_bookers"].get((day, slot))
                user_emoji = await get_user_emoji(uid)
                lines.append(f"{slot} {st} {user_emoji}")

    text = format_html_pre("\n".join(lines))

    # 3) Удаляем старое сообщение, если оно есть
    old_id = ginfo.get("message_id")
    if old_id:
        try:
            await bot.delete_message(chat_id, old_id)
        except:
            pass

    # 4) Строим клавиатуру: кнопки для слотов, которые сейчас `booked`
    builder = InlineKeyboardBuilder()
    for day in ("Сегодня","Завтра"):
        for slot in generate_time_slots():
            st = ginfo["time_slot_statuses"].get((day, slot))
            # Если слот `booked` (ещё не получил финальный статус) — делаем кнопку
            if st == "booked":
                builder.button(
                    text=f"{day} {slot}",
                    callback_data=f"group_time|{group_key}|{day}|{slot}"
                )
        # Разделитель между днями
        builder.button(text="──────────", callback_data="ignore")

    builder.adjust(1)
    kb = builder.as_markup()

    # 5) Отправляем новое сообщение и сохраняем его message_id
    msg = await bot.send_message(
        chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=kb
    )
    ginfo["message_id"] = msg.message_id

    # 6) Обновляем в БД
    if db.db_pool:
        conn = await db.db_pool.acquire()
        try:
            await conn.execute(
                "UPDATE group_financial_data SET message_id=$1 WHERE group_key=$2",
                msg.message_id, group_key
            )
        finally:
            await db.db_pool.release(conn)


async def send_financial_report(bot: Bot):
    """
    Отправляет сводный финансовый отчёт в FINANCIAL_REPORT_GROUP_ID.
    Можно вызывать после каждого изменения.
    """
    if not db.db_pool:
        return
    total_sal = sum(g["salary"] for g in groups_data.values())
    total_cash= sum(g["cash"]   for g in groups_data.values())

    conn = await db.db_pool.acquire()
    try:
        rows = await conn.fetch("SELECT balance FROM users")
        users_total = sum(r["balance"] for r in rows) if rows else 0
    finally:
        await db.db_pool.release(conn)

    itog1 = total_cash - total_sal
    lines = ["═══ 📊 Сводный фин. отчёт 📊 ═══\n"]
    for k, g in groups_data.items():
        lines.append(f"[{k}] Зп: {g['salary']}¥ | Нал: {g['cash']}¥")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines += [
        f"\nИтого зарплата: {total_sal}¥",
        f"Итого наличные: {total_cash}¥",
        f"Итог1 (cash - salary): {itog1}¥",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    # Сводка по пользователям
    conn = await db.db_pool.acquire()
    try:
        rows = await conn.fetch("""
            SELECT u.user_id, u.username, u.balance, e.emoji
            FROM users u LEFT JOIN user_emojis e ON u.user_id=e.user_id
            ORDER BY u.user_id
        """)
        if rows:
            lines.append("═════ 👥 Пользователи 👥 ═════\n")
            for r in rows:
                uname = r["username"] or f"User {r['user_id']}"
                ub = r["balance"]
                ue = r["emoji"] or "❓"
                lines.append(f"{ue} {uname}: {ub}¥")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    finally:
        await db.db_pool.release(conn)

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    lines.append(f"Сумма балансов пользователей: {users_total}¥")
    total_final = itog1 - users_total
    lines.append(f"━━━━ TOTAL (итог1 - балансы) = {total_final}¥ ━━━━")

    report = "<pre>" + "\n".join(lines) + "</pre>"
    try:
        await bot.send_message(FINANCIAL_REPORT_GROUP_ID, report, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка фин. отчёта: {e}")


@router.callback_query(F.data == "view_all_bookings", StateFilter("*"))
async def cmd_all(cb: CallbackQuery, state: FSMContext):
    """
    Пример обработчика для просмотра всех броней (если вам нужно).
    """
    lang = await get_user_language(cb.from_user.id)
    from utils.text_utils import format_html_pre

    group_times = {}
    for gk, g in groups_data.items():
        for d in ("Сегодня", "Завтра"):
            t = g["booked_slots"].get(d, [])
            if t:
                group_times.setdefault(gk, {})[d] = t

    if not group_times:
        text = get_message(lang, "no_active_bookings")
        try:
            await cb.message.edit_text(text)
        except TelegramBadRequest:
            await safe_delete_and_answer(cb.message, text)
        return await cb.answer()

    lines = []
    for day in ("Сегодня", "Завтра"):
        disp = get_message(lang, "today") if day == "Сегодня" else get_message(lang, "tomorrow")
        lines.append(f"📅 {get_message(lang,'all_bookings_title',day=disp)}")
        if not any(day in v for v in group_times.values()):
            lines.append(get_message(lang, "no_bookings"))
            lines.append("")
            continue

        lines += [
            "╔══════════╦════════════════════╗",
            "║ Группа   ║ Время бронирования ║",
            "╠══════════╬════════════════════╣",
        ]
        for gk, td in group_times.items():
            ts = td.get(day, [])
            if not ts:
                continue
            lines.append(f"║ {gk:<9}║ {ts[0]:<18}║")
            for s in ts[1:]:
                lines.append(f"║ {'':<9}║ {s:<18}║")
            lines.append("╠══════════╬════════════════════╣")

        if lines[-1].startswith("╠"):
            lines[-1] = "╚══════════╩════════════════════╝"
        else:
            lines.append("╚══════════╩════════════════════╝")
        lines.append("")

    text = format_html_pre("\n".join(lines))
    try:
        await cb.message.edit_text(text, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        await safe_delete_and_answer(cb.message, text)
    await cb.answer()

async def safe_delete_and_answer(msg: Message, text: str):
    try:
        await msg.delete()
    except:
        pass
    await msg.answer(text, parse_mode=ParseMode.HTML)

                    await con.execute(
                        "DELETE FROM group_time_slot_statuses "
                        "WHERE group_key=$1 AND day=$2 AND time_slot=$3",
                        gk, day, slot
                    )
        except Exception as e:
            logger.error(f"DB error on delete: {e}")

        # Обновляем сообщение
        await update_group_message(cb.bot, gk)
        return await cb.answer("Слот отменён.")

    # Иначе устанавливаем финальный статус (✅, ✅2 и т.д.)
    emoji = status_mapping.get(code)
    ginfo["time_slot_statuses"][(day, slot)] = emoji

    # Запоминаем в БД (status и status_code)
    uid = ginfo["slot_bookers"].get((day, slot))
    if db.db_pool:
        try:
            async with db.db_pool.acquire() as con:
                await con.execute(
                    "UPDATE bookings SET status_code=$1, status=$2 "
                    "WHERE group_key=$3 AND day=$4 AND time_slot=$5",
                    code, emoji, gk, day, slot
                )
                # Обновляем (или вставляем) статусы
                await con.execute(
                    """
                    INSERT INTO group_time_slot_statuses
                      (group_key, day, time_slot, status, user_id)
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT (group_key, day, time_slot)
                    DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                    """,
                    gk, day, slot, emoji, uid
                )
        except Exception as e:
            logger.error(f"DB error: {e}")

    # Применим, если нужно, награду для SPECIAL_USER_ID
    await apply_special_user_reward(code, cb.bot)

    # После выбора статуса предлагаем выбрать способ оплаты (cash/beznal/agent)
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Наличные", callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|cash"),
        InlineKeyboardButton(text="Безнал",   callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|beznal"),
        InlineKeyboardButton(text="Агент",    callback_data=f"payment_method|{gk}|{day}|{slot}|{code}|agent"),
    ]])
    await cb.message.edit_text("Выберите способ оплаты:", parse_mode=ParseMode.HTML, reply_markup=pay_kb)
    await cb.answer()


async def apply_special_user_reward(status_code: str, bot: Bot):
    amount = special_payments.get(status_code, 0)
    if amount <= 0 or not db.db_pool:
        return
    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", SPECIAL_USER_ID)
        if row:
            new = row["balance"] + amount
            await conn.execute("UPDATE users SET balance=$1 WHERE user_id=$2", new, SPECIAL_USER_ID)
        else:
            new = amount
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                SPECIAL_USER_ID, "Special User", amount
            )
    finally:
        await db.db_pool.release(conn)
    try:
        await bot.send_message(SPECIAL_USER_ID, f"Вам начислено дополнительно {amount}¥.\nТекущий баланс: {new}¥")
    except:
        pass


@router.callback_query(F.data.startswith("payment_method|"))
async def process_payment_method(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split("|")
    _, gk, day, slot, code, method = parts
    lang = await get_user_language(cb.from_user.id)
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer(get_message(lang, "no_permission"), show_alert=True)

    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer(get_message(lang, "no_permission"), show_alert=True)

    if not db.db_pool:
        return await cb.answer("Нет подключения к БД", show_alert=True)

    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot,
        )
    finally:
        await db.db_pool.release(conn)
    if not row:
        return await cb.answer(get_message(lang, "no_such_booking"), show_alert=True)

    await cb.answer()
    if method in ("cash", "beznal"):
        txt = get_message(lang, "enter_payment_amount")
        await state.update_data(
            group_key=gk, day=day, time_slot=slot, status_code=code, payment_method=method
        )
        try:
            await cb.bot.edit_message_text(
                chat_id=cb.message.chat.id,
                message_id=cb.message.message_id,
                text=format_html_pre(txt),
                parse_mode=ParseMode.HTML,
            )
        except TelegramBadRequest:
            pass
        await state.set_state(BookPaymentStates.waiting_for_amount)
    else:
        # Агент
        await handle_agent_payment(cb, gk, day, slot, code)


async def handle_agent_payment(cb: CallbackQuery, gk: str, day: str, slot: str, status_code: str):
    """
    При 'Агент' своя логика расчётов, если требуется.
    """
    bot = cb.bot
    uid = cb.from_user.id
    lang = await get_user_language(uid)
    emoji = status_mapping.get(status_code)
    if not emoji:
        return await cb.answer("Некорректный статус!", show_alert=True)
    ginfo = groups_data.get(gk)
    if not ginfo:
        return await cb.answer("Нет такой группы!", show_alert=True)

    # Ниже упрощённая логика, у вас может быть своя
    base = salary_options[ginfo["salary_option"]].get(emoji, 0)
    deduct_map = {"0": 1500, "1": 2100, "2": 3000, "3": 4500}
    deduct = deduct_map.get(status_code, 0)

    ginfo["salary"] += base
    conn = await db.db_pool.acquire()
    try:
        await conn.execute("UPDATE group_financial_data SET salary=$1 WHERE group_key=$2", ginfo["salary"], gk)
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot,
        )
        if not row:
            return await cb.answer(get_message(lang, "no_such_booking"), show_alert=True)
        booked = row["user_id"]
        await update_user_financial_info(booked, -deduct, bot)
        bal_row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", booked)
        bal = bal_row["balance"] if bal_row else 0
        msg = get_message(lang, "changed_balance_user", op="-", amount=deduct, balance=bal)
        await bot.send_message(booked, format_html_pre(msg), parse_mode=ParseMode.HTML)
    finally:
        await db.db_pool.release(conn)

    # Обновляем сообщение в группе
    try:
        await update_group_message(bot, gk)
    except TelegramBadRequest:
        pass

    await send_financial_report(bot)
    await cb.answer("Оплата (agent) учтена.")


async def update_user_financial_info(user_id: int, net_amount: int, bot: Bot):
    """
    Прибавляем (или вычитаем, если net_amount < 0) net_amount к балансу и профиту user_id
    """
    if not db.db_pool:
        return
    try:
        member = await bot.get_chat_member(user_id, user_id)
        uname = member.user.username or f"{member.user.first_name} {member.user.last_name}"
    except:
        uname = f"User_{user_id}"
    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow(
            "SELECT balance, profit, monthly_profit FROM users WHERE user_id=$1", user_id
        )
        if row:
            b, p, m = row["balance"], row["profit"], row["monthly_profit"]
            nb, np, nm = b + net_amount, p + net_amount, m + net_amount
            await conn.execute(
                "UPDATE users SET balance=$1, profit=$2, monthly_profit=$3, username=$4 WHERE user_id=$5",
                nb, np, nm, uname, user_id
            )
        else:
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                user_id, uname, net_amount
            )
    finally:
        await db.db_pool.release(conn)


async def apply_additional_payment(user_id: int, status_code: str, bot: Bot):
    """
    Если нужно доплачивать особому пользователю (SPECIAL_USER_ID), не путать с apply_special_user_reward().
    Можно объединить, если логика дублируется.
    """
    if user_id != SPECIAL_USER_ID:
        return
    extra = special_payments.get(status_code, 0)
    if extra <= 0:
        return
    if not db.db_pool:
        return

    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", user_id)
        if row:
            newb = row["balance"] + extra
            await conn.execute("UPDATE users SET balance=$1 WHERE user_id=$2", newb, user_id)
            await bot.send_message(
                user_id,
                f"<pre>Вам начислено дополнительно {extra}¥.\nВаш текущий баланс: {newb}¥</pre>",
                parse_mode=ParseMode.HTML,
            )
        else:
            await conn.execute(
                "INSERT INTO users (user_id, username, balance, profit, monthly_profit) "
                "VALUES ($1,$2,$3,$3,$3)",
                user_id, "Special User", extra
            )
            await bot.send_message(
                user_id,
                f"<pre>Вам начислено дополнительно {extra}¥.\nВаш текущий баланс: {extra}¥</pre>",
                parse_mode=ParseMode.HTML,
            )
    finally:
        await db.db_pool.release(conn)


@router.message(StateFilter(BookPaymentStates.waiting_for_amount), F.text)
async def process_payment_amount(message: Message, state: FSMContext):
    """
    Обработка цифры, введённой админом (сумма оплаты).
    """
    user = message.from_user
    lang = await get_user_language(user.id)
    data = await state.get_data()
    gk, day, slot = data["group_key"], data["day"], data["time_slot"]
    code, method = data["status_code"], data["payment_method"]

    try:
        amt = int(message.text.strip())
    except ValueError:
        return await message.reply(format_html_pre(get_message(lang, "incorrect_input")),
                                   parse_mode=ParseMode.HTML)

    emoji = status_mapping.get(str(code))
    if not emoji:
        await state.clear()
        return await message.reply(get_message(lang, "invalid_data"))

    if not db.db_pool:
        await state.clear()
        return await message.reply("Нет соединения с БД.")

    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot,
        )
        if not row:
            await state.clear()
            return await message.reply(get_message(lang, "no_such_booking"))
        booked = row["user_id"]

        await conn.execute(
            "UPDATE bookings SET payment_method=$1, amount=$2 "
            "WHERE group_key=$3 AND day=$4 AND time_slot=$5 AND user_id=$6",
            method, amt, gk, day, slot, booked,
        )

        base = salary_options[groups_data[gk]["salary_option"]].get(emoji, 0)
        deduct_map = {"0": 1500, "1": 2100, "2": 3000, "3": 4500}
        deduct = deduct_map.get(str(code), 0)

        groups_data[gk]["salary"] += base
        await conn.execute("UPDATE group_financial_data SET salary=$1 WHERE group_key=$2",
                           groups_data[gk]["salary"], gk)

        if method == "cash":
            groups_data[gk]["cash"] += amt
            await conn.execute("UPDATE group_financial_data SET cash=$1 WHERE group_key=$2",
                               groups_data[gk]["cash"], gk)

        net = amt - deduct
        await update_user_financial_info(booked, net, message.bot)
        await apply_additional_payment(booked, str(code), message.bot)

        # Если есть distribution_variant, начисляем целевому пользователю
        var = groups_data[gk].get("distribution_variant")
        dist_data = distribution_variants.get(var, distribution_variants["variant_400"])
        dist_amt = dist_data.get(str(code), 0)
        tgt = groups_data[gk].get("target_id")
        if dist_amt > 0 and tgt:
            await update_user_financial_info(tgt, dist_amt, message.bot)
    finally:
        await db.db_pool.release(conn)

    try:
        await update_group_message(message.bot, gk)
    except TelegramBadRequest:
        pass

    await send_financial_report(message.bot)
    await state.clear()
    await message.answer(f"Учли оплату {amt} (метод={method}), статус={emoji}.")


async def update_group_message(bot: Bot, group_key: str):
    """
    Перерисовывает сообщение в группе (chat_id, message_id),
    показывая актуальные статусы слотов и кнопки для тех, что ещё в состоянии 'booked'.
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from utils.text_utils import format_html_pre

    ginfo = groups_data[group_key]
    chat_id = ginfo["chat_id"]
    user_lang = "ru"  # при желании можно хранить язык для группы отдельно

    # 1) Формируем текст (шапка, финансы и т.д.)
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"━━━━━━  🌹🌹 {group_key} 🌹🌹  ━━━━━━",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{get_message(user_lang,'salary')}: {ginfo.get('salary',0)}¥",
        f"{get_message(user_lang,'cash')}:   {ginfo.get('cash',0)}¥",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {get_message(user_lang,'booking_report')} ⏰",
    ]

    # Для отображения финальных статусов нам нужно знать эмодзи юзеров
    async def get_user_emoji(uid: int) -> str:
        if not uid or not db.db_pool:
            return "❓"
        try:
            async with db.db_pool.acquire() as con:
                row = await con.fetchrow("SELECT emoji FROM user_emojis WHERE user_id=$1", uid)
                if row and row["emoji"]:
                    return row["emoji"].split(",")[0]
        except:
            pass
        return "❓"

    # 2) Генерируем блоки для Сегодня/Завтра
    final_statuses = {'❌❌❌','✅','✅2','✅✅','✅✅✅'}
    for day in ("Сегодня", "Завтра"):
        lines.append(f"\n{day}:")
        for slot in generate_time_slots():
            st = ginfo["time_slot_statuses"].get((day, slot))
            if st and st in final_statuses:
                # Слот уже имеет окончательный статус -> показываем в тексте
                uid = ginfo["slot_bookers"].get((day, slot))
                user_emoji = await get_user_emoji(uid)
                lines.append(f"{slot} {st} {user_emoji}")

    text = format_html_pre("\n".join(lines))

    # 3) Удаляем старое сообщение, если оно есть
    old_id = ginfo.get("message_id")
    if old_id:
        try:
            await bot.delete_message(chat_id, old_id)
        except:
            pass

    # 4) Строим клавиатуру: кнопки для слотов, которые сейчас `booked`
    builder = InlineKeyboardBuilder()
    for day in ("Сегодня","Завтра"):
        for slot in generate_time_slots():
            st = ginfo["time_slot_statuses"].get((day, slot))
            # Если слот `booked` (ещё не получил финальный статус) — делаем кнопку
            if st == "booked":
                builder.button(
                    text=f"{day} {slot}",
                    callback_data=f"group_time|{group_key}|{day}|{slot}"
                )
        # Разделитель между днями
        builder.button(text="──────────", callback_data="ignore")

    builder.adjust(1)
    kb = builder.as_markup()

    # 5) Отправляем новое сообщение и сохраняем его message_id
    msg = await bot.send_message(
        chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=kb
    )
    ginfo["message_id"] = msg.message_id

    # 6) Обновляем в БД
    if db.db_pool:
        conn = await db.db_pool.acquire()
        try:
            await conn.execute(
                "UPDATE group_financial_data SET message_id=$1 WHERE group_key=$2",
                msg.message_id, group_key
            )
        finally:
            await db.db_pool.release(conn)


async def send_financial_report(bot: Bot):
    """
    Отправляет сводный финансовый отчёт в FINANCIAL_REPORT_GROUP_ID.
    Можно вызывать после каждого изменения.
    """
    if not db.db_pool:
        return
    total_sal = sum(g["salary"] for g in groups_data.values())
    total_cash= sum(g["cash"]   for g in groups_data.values())

    conn = await db.db_pool.acquire()
    try:
        rows = await conn.fetch("SELECT balance FROM users")
        users_total = sum(r["balance"] for r in rows) if rows else 0
    finally:
        await db.db_pool.release(conn)

    itog1 = total_cash - total_sal
    lines = ["═══ 📊 Сводный фин. отчёт 📊 ═══\n"]
    for k, g in groups_data.items():
        lines.append(f"[{k}] Зп: {g['salary']}¥ | Нал: {g['cash']}¥")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines += [
        f"\nИтого зарплата: {total_sal}¥",
        f"Итого наличные: {total_cash}¥",
        f"Итог1 (cash - salary): {itog1}¥",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    # Сводка по пользователям
    conn = await db.db_pool.acquire()
    try:
        rows = await conn.fetch("""
            SELECT u.user_id, u.username, u.balance, e.emoji
            FROM users u LEFT JOIN user_emojis e ON u.user_id=e.user_id
            ORDER BY u.user_id
        """)
        if rows:
            lines.append("═════ 👥 Пользователи 👥 ═════\n")
            for r in rows:
                uname = r["username"] or f"User {r['user_id']}"
                ub = r["balance"]
                ue = r["emoji"] or "❓"
                lines.append(f"{ue} {uname}: {ub}¥")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    finally:
        await db.db_pool.release(conn)

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    lines.append(f"Сумма балансов пользователей: {users_total}¥")
    total_final = itog1 - users_total
    lines.append(f"━━━━ TOTAL (итог1 - балансы) = {total_final}¥ ━━━━")

    report = "<pre>" + "\n".join(lines) + "</pre>"
    try:
        await bot.send_message(FINANCIAL_REPORT_GROUP_ID, report, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка фин. отчёта: {e}")


@router.callback_query(F.data == "view_all_bookings", StateFilter("*"))
async def cmd_all(cb: CallbackQuery, state: FSMContext):
    """
    Пример обработчика для просмотра всех броней (если вам нужно).
    """
    lang = await get_user_language(cb.from_user.id)
    from utils.text_utils import format_html_pre

    group_times = {}
    for gk, g in groups_data.items():
        for d in ("Сегодня", "Завтра"):
            t = g["booked_slots"].get(d, [])
            if t:
                group_times.setdefault(gk, {})[d] = t

    if not group_times:
        text = get_message(lang, "no_active_bookings")
        try:
            await cb.message.edit_text(text)
        except TelegramBadRequest:
            await safe_delete_and_answer(cb.message, text)
        return await cb.answer()

    lines = []
    for day in ("Сегодня", "Завтра"):
        disp = get_message(lang, "today") if day == "Сегодня" else get_message(lang, "tomorrow")
        lines.append(f"📅 {get_message(lang,'all_bookings_title',day=disp)}")
        if not any(day in v for v in group_times.values()):
            lines.append(get_message(lang, "no_bookings"))
            lines.append("")
            continue

        lines += [
            "╔══════════╦════════════════════╗",
            "║ Группа   ║ Время бронирования ║",
            "╠══════════╬════════════════════╣",
        ]
        for gk, td in group_times.items():
            ts = td.get(day, [])
            if not ts:
                continue
            lines.append(f"║ {gk:<9}║ {ts[0]:<18}║")
            for s in ts[1:]:
                lines.append(f"║ {'':<9}║ {s:<18}║")
            lines.append("╠══════════╬════════════════════╣")

        if lines[-1].startswith("╠"):
            lines[-1] = "╚══════════╩════════════════════╝"
        else:
            lines.append("╚══════════╩════════════════════╝")
        lines.append("")

    text = format_html_pre("\n".join(lines))
    try:
        await cb.message.edit_text(text, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        await safe_delete_and_answer(cb.message, text)
    await cb.answer()

async def safe_delete_and_answer(msg: Message, text: str):
    try:
        await msg.delete()
    except:
        pass
    await msg.answer(text, parse_mode=ParseMode.HTML)
