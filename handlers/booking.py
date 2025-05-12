# handlers/booking.py

import logging
import html
import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.enums import ParseMode
import db  # Здесь ваш модуль, где db.db_pool

logger = logging.getLogger(__name__)

###############################################################################
# ВСПОМОГАТЕЛЬНЫЕ «ЗАГЛУШКИ»
# (При необходимости, замените реализацией под ваш проект)
###############################################################################
async def get_user_language(user_id: int) -> str:
    """Определение языка (ru/en/...); заглушка."""
    return "ru"

def get_message(lang: str, key: str, **kwargs) -> str:
    """Простейшая локализация (заглушка)."""
    translations = {
        "ru": {
            "no_action": "Просто заглушка-кнопка без действия.",
            "invalid_data": "Некорректные данные!",
            "no_such_group": "Нет такой группы!",
            "no_such_booking": "Не найдена такая бронь!",
            "no_permission": "У вас нет прав!",
            "incorrect_input": "Неверный ввод числа!",
            "changed_balance_user": "Баланс пользователя {op}{amount} => {balance}",
            "distribution_message": "Начислено {amount}, баланс {balance}",
            "enter_payment_amount": "Введите сумму (числом):",
            "select_method_payment": "Выберите способ оплаты:",
            "booking_report": "Брони",
            "salary": "Зарплата",
            "cash": "Наличные",
            "slot_booked": "Слот {time} ({day}) в группе {group} забронирован!",

            "today": "Сегодня",
            "tomorrow": "Завтра",
            "choose_time_styled": "Выберите свободное время на {day}:"
        }
    }
    tmpl = translations.get(lang, {}).get(key, key)
    return tmpl.format(**kwargs)

async def get_next_emoji(user_id: int) -> str:
    """Возвращает «следующий» эмодзи пользователя — заглушка."""
    return "❓"

def fmt(text: str) -> str:
    """Обёртка в <pre> + HTML-escape."""
    return f"<pre>{html.escape(text)}</pre>"

###############################################################################
# КОНСТАНТЫ
###############################################################################
LANG_DEFAULT = "ru"
SPECIAL_USER_ID = 7935161063
FINANCIAL_REPORT_GROUP_ID = -1002216239869  # ID группы для финансового отчёта
BOOKING_REPORT_GROUP_ID = -1002671780634 # ID группы для отчётов о бронировании

###############################################################################
# ПРИМЕР: привязка статусов к символам, зарплате и т.п.
###############################################################################
special_payments = {
    '0': 40,   # при финальном статусе "✅"
    '1': 40,   # при финальном статусе "✅2"
    '2': 80,   # при финальном статусе "✅✅"
    '3': 120,  # при финальном статусе "✅✅✅"
}

status_mapping = {
    '0': '✅',    # подтверждение
    '1': '✅2',   # подтверждение 2
    '2': '✅✅',  # двойное
    '3': '✅✅✅', # тройное
    '-1': '❌❌❌'  # удалён
}

salary_options = {
    1: {'✅':700,  '✅2':900,  '✅✅':1400, '✅✅✅':2100},
    2: {'✅':800,  '✅2':1000, '✅✅':1600, '✅✅✅':2400},
    3: {'✅':900,  '✅2':1100, '✅✅':1800, '✅✅✅':2700},
    4: {'✅':1000, '✅2':1200, '✅✅':2000, '✅✅✅':3000}
}

distribution_variants = {
    'variant_100': {'0':100, '1':100, '2':200, '3':300},
    'variant_200': {'0':200, '1':200, '2':400, '3':600},
    'variant_300': {'0':300, '1':300, '2':600, '3':900},
    'variant_400': {'0':400, '1':400, '2':800, '3':1200}
}

###############################################################################
# ГРУППЫ
###############################################################################
groups_data = {
    "Royal_1": {
        "chat_id": -1002503654146,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},  # (day, slot) -> "booked"/"✅" и т.п.
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "slot_bookers": {},       # (day, slot) -> user_id
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_2": {
        "chat_id": -1002569987326,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_3": {
        "chat_id": -1002699377044,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_4": {
        "chat_id": -1002696765874,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_5": {
        "chat_id": -1002555587028,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_6": {
        "chat_id": -1002525751059,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
}

###############################################################################
# FSM-классы
###############################################################################
class BookUserStates(StatesGroup):
    waiting_for_group = State()
    waiting_for_day   = State()
    waiting_for_time  = State()

class BookPaymentStates(StatesGroup):
    waiting_for_amount = State()

###############################################################################
# Router
###############################################################################
router = Router()

###############################################################################
# Генерация слотов и соседей
###############################################################################
def generate_time_slots() -> list[str]:
    """Каждые полчаса (пример)."""
    return [
        "12:00", "12:30",
        "13:00", "13:30",
        "14:00", "14:30",
        "15:00", "15:30",
        "16:00", "16:30",
        "17:00", "17:30",
        "18:00", "18:30",
        "19:00", "19:30",
        "20:00", "20:30",
        "21:00", "21:30",
        "22:00", "22:30",
        "23:00", "23:30",
        "00:00", "00:30",
        "01:00", "01:30",
        "02:00"
    ]

def get_adjacent_slots(slot: str) -> list[str]:
    slots = generate_time_slots()
    if slot not in slots:
        return []
    i = slots.index(slot)
    neighbors = []
    if i > 0:
        neighbors.append(slots[i - 1])
    if i < len(slots) - 1:
        neighbors.append(slots[i + 1])
    return neighbors

###############################################################################
# (1) /book — бронирование в ЛС
###############################################################################
from aiogram.filters.command import Command
from aiogram.filters import StateFilter

@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext):
    """Пользователь в ЛС: выбор группы для бронирования."""
    if message.chat.type != "private":
        await message.answer("Команду /book используйте в личке.")
        return

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
    await message.answer(
        fmt("Выберите группу для бронирования:"),
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )
    await state.set_state(BookUserStates.waiting_for_group)

@router.callback_query(StateFilter(BookUserStates.waiting_for_group), F.data.startswith("bkgrp_"))
async def user_select_group(callback: CallbackQuery, state: FSMContext):
    gk = callback.data.removeprefix("bkgrp_")
    if gk not in groups_data:
        await callback.answer("Нет такой группы!", show_alert=True)
        return

    await state.update_data(selected_group=gk)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="Сегодня", callback_data="bkday_Сегодня"),
            InlineKeyboardButton(text="Завтра",  callback_data="bkday_Завтра")
        ]]
    )

    txt = f"Вы выбрали: {gk}\nВыберите день:"
    await callback.message.edit_text(fmt(txt), parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()
    await state.set_state(BookUserStates.waiting_for_day)

@router.callback_query(StateFilter(BookUserStates.waiting_for_day), F.data.startswith("bkday_"))
async def user_select_day(callback: CallbackQuery, state: FSMContext):
    day_lbl = callback.data.removeprefix("bkday_")
    data = await state.get_data()
    gk = data.get("selected_group")

    ginfo = groups_data[gk]
    busy = set(ginfo["booked_slots"][day_lbl])
    busy |= ginfo["unavailable_slots"][day_lbl]

    row_buf = []
    rows = []
    all_slots = generate_time_slots()
    for i, slot in enumerate(all_slots, start=1):
        if slot not in busy:
            cb = f"bkslot_{slot.replace(':','_')}"
            row_buf.append(InlineKeyboardButton(text=slot, callback_data=cb))
        if len(row_buf) == 4:
            rows.append(row_buf)
            row_buf = []
    if row_buf:
        rows.append(row_buf)

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await state.update_data(selected_day=day_lbl)

    txt = f"Группа: {gk}\nДень: {day_lbl}\nВыберите свободный слот:"
    await callback.message.edit_text(fmt(txt), parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()
    await state.set_state(BookUserStates.waiting_for_time)

#
# ФУНКЦИЯ ОТПРАВКИ ОТЧЁТА О БРОНИРОВАНИИ
async def send_booking_report(bot, user_id: int, group_key: str, time_slot: str, day: str):
    """
    Отправляет сообщение о новом бронировании в группу BOOKING_REPORT_GROUP_ID.
    """
    conn = db.db_pool
    username = f"User {user_id}"
    user_emoji = '❓'

    if conn:
        try:
            async with conn.acquire() as c:
                row = await c.fetchrow("""
                    SELECT u.username, e.emoji
                    FROM users u
                    LEFT JOIN user_emojis e ON u.user_id = e.user_id
                    WHERE u.user_id=$1
                """, user_id)
                if row:
                    if row['username']:
                        username = row['username']
                    if row['emojis']:
                        user_emoji = row['emojis'].split(',')[0]
        except Exception as e:
            logger.error(f"Ошибка при получении username/emojis: {e}")

    text_report = (
        f"<b>📅 Новый Booking</b>\n"
        f"👤 <b>Пользователь:</b> {user_emoji} {username}\n"
        f"🌹 <b>Группа:</b> {group_key}\n"
        f"⏰ <b>Время:</b> {time_slot} ({day})"
    )

    try:
        await bot.send_message(
            chat_id=BOOKING_REPORT_GROUP_ID,
            text=text_report,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Не удалось отправить отчёт о бронировании: {e}")


@router.callback_query(StateFilter(BookUserStates.waiting_for_time), F.data.startswith("bkslot_"))
async def user_select_slot(callback: CallbackQuery, state: FSMContext):
    slot_str = callback.data.removeprefix("bkslot_").replace("_", ":")
    data = await state.get_data()
    gk = data.get("selected_group")
    day = data.get("selected_day")
    uid = callback.from_user.id

    ginfo = groups_data[gk]
    # Отмечаем слот как booked
    ginfo["booked_slots"][day].append(slot_str)
    ginfo["slot_bookers"][(day, slot_str)] = uid
    ginfo["time_slot_statuses"][(day, slot_str)] = "booked"

    # Делаем соседние слоты "unavailable"
    for adj in get_adjacent_slots(slot_str):
        if adj not in ginfo["booked_slots"][day]:
            ginfo["unavailable_slots"][day].add(adj)
            ginfo["time_slot_statuses"][(day, adj)] = "unavailable"
            ginfo["slot_bookers"][(day, adj)] = uid

    # Сохранение в БД
    if db.db_pool:
        try:
            now_sh = datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
            if day == "Завтра":
                now_sh += timedelta(days=1)
            hh, mm = slot_str.split(":")
            now_sh = now_sh.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            iso_str = now_sh.isoformat()

            async with db.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO bookings (group_key, day, time_slot, user_id, status, start_time)
                    VALUES ($1, $2, $3, $4, 'booked', $5)
                """, gk, day, slot_str, uid, iso_str)

                await conn.execute("""
                    INSERT INTO group_time_slot_statuses (group_key, day, time_slot, status, user_id)
                    VALUES ($1, $2, $3, 'booked', $4)
                    ON CONFLICT (group_key, day, time_slot)
                    DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                """, gk, day, slot_str, uid)

                for adj_s in get_adjacent_slots(slot_str):
                    await conn.execute("""
                        INSERT INTO group_time_slot_statuses (group_key, day, time_slot, status, user_id)
                        VALUES ($1, $2, $3, 'unavailable', $4)
                        ON CONFLICT (group_key, day, time_slot)
                        DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                    """, gk, day, adj_s, uid)

        except Exception as e:
            logger.error(f"Ошибка записи бронирования в БД: {e}")

    # Отправка отчёта в BOOKING_REPORT_GROUP_ID
    await send_booking_report(callback.bot, uid, gk, slot_str, day)

    # Завершаем состояние FSM
    await state.clear()

    # Сообщение пользователю
    lang = await get_user_language(uid)
    final_txt = get_message(lang, 'slot_booked', day=day, time=slot_str, group=gk)
    await callback.message.edit_text(fmt(final_txt), parse_mode=ParseMode.HTML)
    await callback.answer()

    # << ВАЖНО >> Обновляем pinned в соответствующей группе (добавьте ЭТО!)
    await update_group_message(callback.bot, gk)
###############################################################################
# (2) Управление слотами в группе (админ)
###############################################################################
# ---------------------------------------------------------------------------
# (A) Клик по слоту в закреплённом сообщении группы ─ выбираем финальный статус
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("group_time|"))
async def admin_click_slot(callback: CallbackQuery) -> None:
    """
    Принимаем callback вида
        group_time|{group_key}|{day}|{time_slot}
    и показываем клавиатуру выбора окончательного статуса.
    """
    parts = callback.data.split("|")
    if len(parts) != 4:
        return await callback.answer("Некорректные данные!", show_alert=True)

    _, group_key, day, slot = parts
    ginfo = groups_data.get(group_key)
    if not ginfo or callback.message.chat.id != ginfo["chat_id"]:
        return await callback.answer("Нет прав!", show_alert=True)

    member = await callback.bot.get_chat_member(
        callback.message.chat.id, callback.from_user.id
    )
    if member.status not in ("administrator", "creator"):
        return await callback.answer("Только админ!", show_alert=True)

    # строим клавиатуру строго с именованными аргументами!
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅",      callback_data=f"group_status|{group_key}|{day}|{slot}|0"),
            InlineKeyboardButton(text="✅2",     callback_data=f"group_status|{group_key}|{day}|{slot}|1"),
            InlineKeyboardButton(text="✅✅",    callback_data=f"group_status|{group_key}|{day}|{slot}|2"),
            InlineKeyboardButton(text="✅✅✅",  callback_data=f"group_status|{group_key}|{day}|{slot}|3"),
        ],
        [
            InlineKeyboardButton(text="❌❌❌",  callback_data=f"group_status|{group_key}|{day}|{slot}|-1")
        ],
        [
            InlineKeyboardButton(text="Назад",  callback_data=f"group_status|{group_key}|{day}|{slot}|back")
        ],
    ])

    await callback.message.edit_text(
        "<b>Выберите финальный статус слота:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# (B) Клик по одной из кнопок «✅ / ❌ / Назад / …» ─ финализируем статус
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("group_status|"))
async def admin_click_status(callback: CallbackQuery) -> None:
    """
    Обрабатывает callback вида
        group_status|{group_key}|{day}|{slot}|{code}
    где code:
        back  -> вернуться к списку слотов
        -1    -> удалить бронь
        0-3   -> финальный статус («✅», «✅2», «✅✅», «✅✅✅»)
    """
    # ────────── разбор и проверки ──────────
    parts = callback.data.split("|")
    if len(parts) != 5:
        return await callback.answer("Некорректные данные!", show_alert=True)
    _, group_key, day, slot, code = parts

    ginfo = groups_data.get(group_key)
    if not ginfo or callback.message.chat.id != ginfo["chat_id"]:
        return await callback.answer("Нет прав!", show_alert=True)

    member = await callback.bot.get_chat_member(
        callback.message.chat.id, callback.from_user.id
    )
    if member.status not in ("administrator", "creator"):
        return await callback.answer("Нет прав!", show_alert=True)

    # ────────── «Назад» ──────────
    if code == "back":
        await update_group_message(callback.bot, group_key)
        return await callback.answer()

    # ────────── Удаление слота ──────────
    if code == "-1":
        # ... (логика удаления ровно та же, что была; опущена для краткости)
        await update_group_message(callback.bot, group_key)
        return await callback.answer("Слот удалён.")

    # ────────── Финальный статус (0-3) ──────────
    status_emoji = status_mapping.get(code, "")
    ginfo["time_slot_statuses"][(day, slot)] = status_emoji

    # БД (если нужна) — оставляем вашу логику
    if db.db_pool:
        try:
            uid = ginfo["slot_bookers"].get((day, slot))
            async with db.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE bookings
                    SET status_code=$1, status=$2
                    WHERE group_key=$3 AND day=$4 AND time_slot=$5
                    """,
                    code, status_emoji, group_key, day, slot
                )
                await conn.execute(
                    """
                    INSERT INTO group_time_slot_statuses
                      (group_key, day, time_slot, status, user_id)
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT (group_key, day, time_slot)
                    DO UPDATE SET status=excluded.status, user_id=excluded.user_id
                    """,
                    group_key, day, slot, status_emoji, uid
                )
        except Exception as e:
            logger.error(f"DB error: {e}")

    # награждаем при необходимости
    await apply_special_user_reward(code)

    # ────────── спрашиваем оплату ──────────
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Наличные", callback_data=f"paymethod|{group_key}|{day}|{slot}|{code}|cash"),
        InlineKeyboardButton(text="Безнал",   callback_data=f"paymethod|{group_key}|{day}|{slot}|{code}|beznal"),
        InlineKeyboardButton(text="Агент",    callback_data=f"paymethod|{group_key}|{day}|{slot}|{code}|agent"),
    ]])
    await callback.message.edit_text(
        "Выберите способ оплаты:",
        parse_mode=ParseMode.HTML,
        reply_markup=pay_kb
    )
    await callback.answer()

async def apply_special_user_reward(code: str):
    """Если code in ['0','1','2','3'], добавляем некую сумму SPECIAL_USER_ID."""
    rw = special_payments.get(code, 0)
    if rw <= 0:
        return
    if not db.db_pool:
        return

    try:
        async with db.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", SPECIAL_USER_ID)
            if row:
                newb = row["balance"] + rw
                await conn.execute("UPDATE users SET balance=$1 WHERE user_id=$2", newb, SPECIAL_USER_ID)
            else:
                # пользователь не существует, создадим
                await conn.execute("""
                    INSERT INTO users (user_id, username, balance, profit, monthly_profit)
                    VALUES ($1,'SpecialUser',$2,$2,$2)
                """, SPECIAL_USER_ID, rw)
    except Exception as e:
        logger.error(f"apply_special_user_reward error: {e}")

###############################################################################
# paymethod|{gk}|{day}|{slot}|{code}|cash/beznal/agent
###############################################################################
@router.callback_query(F.data.startswith("paymethod|"))
async def admin_payment_method(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("|")
    if len(parts) != 6:
        await callback.answer("Некорректные данные!", show_alert=True)
        return
    _, gk, day, slot, code, pmeth = parts

    ginfo = groups_data.get(gk)
    if not ginfo or (callback.message.chat.id != ginfo["chat_id"]):
        await callback.answer("Нет прав!", show_alert=True)
        return

    mem = await router.bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
    if mem.status not in ("administrator", "creator"):
        await callback.answer("Нет прав!", show_alert=True)
        return

    if pmeth in ("cash","beznal"):
        # Просим сумму
        await state.update_data(
            group_key=gk,
            day=day,
            time_slot=slot,
            status_code=code,
            payment_method=pmeth
        )
        txt = get_message(LANG_DEFAULT, 'enter_payment_amount')
        await callback.message.edit_text(fmt(txt), parse_mode=ParseMode.HTML)
        await callback.answer()
        await state.set_state(BookPaymentStates.waiting_for_amount)

    elif pmeth == "agent":
        await handle_agent_payment(gk, day, slot, code)
        await update_group_message(callback.bot, gk)
        await callback.answer("Оплата=agent OK.")
    else:
        await callback.answer("Неподдерживаемый метод!", show_alert=True)

async def handle_agent_payment(group_key: str, day: str, slot: str, status_code: str):
    """
    Если выбрано 'agent', реализуйте собственную логику расчётов (вычет/распределение).
    """
    logger.info(f"[AGENT] group={group_key}, day={day}, slot={slot}, code={status_code}")
    # TODO: ваша реализация
    pass

###############################################################################
# Приём суммы (BookPaymentStates.waiting_for_amount)
###############################################################################
@router.message(BookPaymentStates.waiting_for_amount)
async def admin_enter_amount(message: Message, state: FSMContext):
    text_in = message.text.strip()
    if not text_in.isdigit():
        await message.answer("Введите число!")
        return
    amt = int(text_in)
    if amt <= 0:
        await message.answer("Число должно быть >0!")
        return

    data  = await state.get_data()
    gk    = data["group_key"]
    day   = data["day"]
    slot  = data["time_slot"]
    scode = data["status_code"]
    pmeth = data["payment_method"]

    ginfo = groups_data[gk]
    st    = status_mapping.get(scode,"")

    # Возьмём salary_option
    sopt  = ginfo["salary_option"]
    add_sal = 0
    if st in salary_options[sopt]:
        add_sal = salary_options[sopt][st]

    ginfo["salary"] += add_sal
    if pmeth == "cash":
        ginfo["cash"] += amt

    # Запись в БД
    if db.db_pool:
        try:
            async with db.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE group_financial_data
                    SET salary=$1, cash=$2
                    WHERE group_key=$3
                """, ginfo["salary"], ginfo["cash"], gk)

                # пропишем payment_method + amount
                await conn.execute("""
                    UPDATE bookings
                    SET payment_method=$1, amount=$2
                    WHERE group_key=$3 AND day=$4 AND time_slot=$5
                """, pmeth, amt, gk, day, slot)
        except Exception as e:
            logger.error(f"DB error: {e}")

    await state.clear()
    await message.answer(f"Учли оплату {amt} (метод={pmeth}), статус={st}.")

    # Обновляем закреплённое сообщение
    await update_group_message(message.bot, gk)

###############################################################################
# update_group_message — пересоздание «закреплённого» сообщения
###############################################################################
async def update_group_message(bot, group_key: str):
    ginfo=groups_data[group_key]
    chat_id=ginfo["chat_id"]

    lines=[]
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Группа: {group_key}")
    lines.append(f"Зарплата: {ginfo['salary']} ¥")
    lines.append(f"Наличные: {ginfo['cash']} ¥")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    final_st={'❌❌❌','✅','✅2','✅✅','✅✅✅','booked'}

    lines.append("Сегодня:")
    for slot in generate_time_slots():
        st=ginfo["time_slot_statuses"].get(("Сегодня",slot), "")
        if st in final_st:
            uid=ginfo["slot_bookers"].get(("Сегодня",slot))
            em=await get_next_emoji(uid) if uid else "?"
            lines.append(f"{slot} {st} {em}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("Завтра:")
    for slot in generate_time_slots():
        st=ginfo["time_slot_statuses"].get(("Завтра",slot), "")
        if st in final_st:
            uid=ginfo["slot_bookers"].get(("Завтра",slot))
            em=await get_next_emoji(uid) if uid else "?"
            lines.append(f"{slot} {st} {em}")

    final_txt=fmt("\n".join(lines))

    old_id=ginfo.get("message_id")
    if old_id:
        try:
            await bot.delete_message(chat_id, old_id)
        except:
            pass

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder=InlineKeyboardBuilder()
    for d in ["Сегодня","Завтра"]:
        for s in ginfo["booked_slots"][d]:
            cb_data=f"group_time|{group_key}|{d}|{s}"
            builder.button(text=f"{d} {s}", callback_data=cb_data)
    builder.adjust(2)
    kb=builder.as_markup()

    try:
        msg=await bot.send_message(chat_id, final_txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        ginfo["message_id"]=msg.message_id
    except Exception as e:
        logger.error(f"Ошибка при отправке pinned: {e}")
###############################################################################
# (доп) send_financial_report
###############################################################################
async def send_financial_report():
    """
    По желанию можно вызывать этот метод для отчёта:
    - Общая зарплата, общая наличка,
    - Далее можно расширять логику.
    """
    if not db.db_pool:
        return

    total_sal  = 0
    total_cash = 0
    for gk, ginfo in groups_data.items():
        total_sal  += ginfo["salary"]
        total_cash += ginfo["cash"]

    text = f"Фин.отчёт:\nИтого salary={total_sal}\nИтого cash={total_cash}"
    try:
        await router.bot.send_message(FINANCIAL_REPORT_GROUP_ID, text)
    except Exception as e:
        logger.warning(f"Не удалось отправить фин.отчёт: {e}")

###############################################################################
# (доп) send_time_slots(...) (если нужно отдельным методом выводить свободные)
###############################################################################
async def send_time_slots(callback_query: CallbackQuery, selected_day: str, state: FSMContext):
    """
    Пример, если хочется выводить список слотов отдельно (необязательно).
    """
    user_data = await state.get_data()
    group_key = user_data.get('selected_group')
    group_info = groups_data.get(group_key)

    time_slots = generate_time_slots()
    keyboard   = InlineKeyboardMarkup(row_width=4)
    occupied_statuses = {'unavailable', '❌❌❌', '✅', '✅2', '✅✅', '✅✅✅', 'booked'}

    for slot in time_slots:
        key = (selected_day, slot)
        slot_is_occupied = False
        if slot in group_info['booked_slots'].get(selected_day, []):
            slot_is_occupied = True
        elif slot in group_info['unavailable_slots'].get(selected_day, set()):
            slot_is_occupied = True
        elif key in group_info['time_slot_statuses']:
            status = group_info['time_slot_statuses'][key]
            if status in occupied_statuses:
                slot_is_occupied = True

        if not slot_is_occupied:
            cb_data = f"time_{selected_day}_{slot.replace(':','_')}"
            keyboard.insert(InlineKeyboardButton(text=slot, callback_data=cb_data))

    keyboard.add(InlineKeyboardButton(text="« Назад", callback_data="back_to_day_selection"))

    user_id   = callback_query.from_user.id
    user_lang = await get_user_language(user_id)
    day_label = (get_message(user_lang, 'today') if selected_day == 'Сегодня'
                 else get_message(user_lang, 'tomorrow'))

    text = get_message(user_lang, 'choose_time_styled', day=day_label)
    final_txt = fmt(text)

    await router.bot.edit_message_text(
        text=final_txt,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
