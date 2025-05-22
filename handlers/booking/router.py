import logging
import html
from datetime import timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Router, F, types
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from aiogram.filters.command import Command
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from constants.booking_const import (
    BOOKING_REPORT_GROUP_ID,
    SPECIAL_USER_ID,
    FINANCIAL_REPORT_GROUP_ID,
    GROUP_CHOICE_IMG,
    DAY_CHOICE_IMG,
    TIME_CHOICE_IMG,
    FINAL_BOOKED_IMG,
    special_payments,
    status_mapping,
    distribution_variants,
    groups_data,
)
from constants.salary import salary_options
from utils.user_utils import get_user_language
from utils.text_utils import get_message, format_html_pre
from utils.time_utils import (
    generate_daily_time_slots as generate_time_slots,
    get_adjacent_time_slots,
    get_slot_datetime_shanghai,
)
from db_access.booking_repo import BookingRepo
from handlers.booking.data_manager import BookingDataManager
from app_states import BookUserStates, BookPaymentStates

logger = logging.getLogger(__name__)
router = Router()

# Инициализируем репозиторий с пулом
repo = BookingRepo(db.db_pool)
data_mgr = BookingDataManager(groups_data)


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext):
    await state.clear()
    keys = data_mgr.list_group_keys()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=k, callback_data=f"bkgrp_{k}") for k in keys[i : i + 3]]
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



async def send_time_slots(callback_query: types.CallbackQuery, selected_day: str, state: FSMContext):
    user_data = await state.get_data()
    gk = user_data["selected_group"]
    ginfo = groups_data[gk]

    # Собираем занятые/скрытые слоты
    busy = set(ginfo["booked_slots"].get(selected_day, []))
    for bs in list(busy):
        busy.update(get_adjacent_time_slots(bs))
    busy |= ginfo["unavailable_slots"].get(selected_day, set())
    final = {'❌❌❌', '✅', '✅2', '✅✅', '✅✅✅'}
    for (d, t), st in ginfo["time_slot_statuses"].items():
        if d == selected_day and st in final:
            busy.add(t)

    # Строим клавиатуру свободных слотов
    builder = InlineKeyboardBuilder()
    for slot in generate_time_slots():
        if slot in busy:
            continue
        builder.button(text=slot, callback_data=f"bkslot_{slot.replace(':','_')}")
    builder.button(text="« Назад", callback_data="bkgrp_back")
    builder.adjust(4)
    keyboard = builder.as_markup()

    # Формируем текст
    user_lang = await get_user_language(callback_query.from_user.id)
    day_label = get_message(user_lang, 'today') if selected_day == 'Сегодня' else get_message(user_lang, 'tomorrow')
    text = get_message(user_lang, 'choose_time_styled', day=day_label)
    formatted = format_html_pre(text)

    # Пытаемся заменить медиа на TIME_CHOICE_IMG
    try:
        await callback_query.message.edit_media(
            media=InputMediaPhoto(media=TIME_CHOICE_IMG, caption=formatted),
            reply_markup=keyboard
        )
    except TelegramBadRequest:
        # Если не получилось — отправляем новое фото
        await callback_query.message.answer_photo(
            photo=TIME_CHOICE_IMG, caption=formatted, reply_markup=keyboard
        )

    await callback_query.answer()
    await state.set_state(BookUserStates.waiting_for_time)


@router.callback_query(StateFilter(BookUserStates.waiting_for_time), F.data.startswith("bkslot_"))
async def user_select_time(cb: CallbackQuery, state: FSMContext):
    slot = cb.data.removeprefix("bkslot_").replace("_", ":")
    data = await state.get_data()
    gk, day, uid = data["selected_group"], data["selected_day"], cb.from_user.id

    data_mgr.book_slot(gk, day, slot, uid)
    iso = get_slot_datetime_shanghai(day, slot)
    await repo.add_booking(gk, day, slot, uid, iso)
    await send_booking_report(cb.bot, uid, gk, slot, day)
    await state.clear()

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
    await update_group_message(cb.bot, gk)

@router.callback_query(F.data.startswith("group_time|"))
async def admin_click_slot(cb: CallbackQuery):
    parts = cb.data.split("|")
    _, gk, day, slot = parts
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer("Нет прав!", show_alert=True)
    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer("Только админ!", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=e, callback_data=f"group_status|{gk}|{day}|{slot}|{code}")
         for code, e in status_mapping.items() if code != "-1"],
        [InlineKeyboardButton(text="❌❌❌", callback_data=f"group_status|{gk}|{day}|{slot}|-1")],
        [InlineKeyboardButton(text="Назад", callback_data=f"group_status|{gk}|{day}|{slot}|back")]
    ])

    await cb.message.edit_text("<b>Выберите финальный статус слота:</b>",
                               parse_mode=ParseMode.HTML,
                               reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("group_status|"))
async def admin_click_status(cb: CallbackQuery):
    parts = cb.data.split("|")
    _, gk, day, slot, code = parts
    ginfo = groups_data.get(gk)
    if not ginfo or cb.message.chat.id != ginfo["chat_id"]:
        return await cb.answer("Нет прав!", show_alert=True)
    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await cb.answer("Нет прав!", show_alert=True)

    if code == "back":
        await update_group_message(cb.bot, gk)
        return await cb.answer()

    if code == "-1":
        ginfo["time_slot_statuses"][(day, slot)] = "❌❌❌"
        await update_group_message(cb.bot, gk)
        return await cb.answer("Слот удалён.")

    emoji = status_mapping.get(code)
    ginfo["time_slot_statuses"][(day, slot)] = emoji

    if db.db_pool:
        try:
            uid = ginfo["slot_bookers"].get((day, slot))
            async with db.db_pool.acquire() as con:
                await con.execute(
                    "UPDATE bookings SET status_code=$1, status=$2 "
                    "WHERE group_key=$3 AND day=$4 AND time_slot=$5",
                    code, emoji, gk, day, slot
                )
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

    await apply_special_user_reward(code, cb.bot)

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


async def update_user_financial_info(user_id: int, net_amount: int, bot: Bot):
    try:
        member = await bot.get_chat_member(user_id, user_id)
        uname = member.user.username or f"{member.user.first_name} {member.user.last_name}"
    except:
        uname = "Unknown"
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
    if user_id != SPECIAL_USER_ID:
        return
    extra = special_payments.get(status_code, 0)
    if extra <= 0:
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


async def handle_agent_payment(cb: CallbackQuery, gk: str, day: str, slot: str, status_code: str):
    bot = cb.bot
    uid = cb.from_user.id
    lang = await get_user_language(uid)
    emoji = status_mapping.get(status_code)
    if not emoji:
        return await cb.answer("Некорректный статус!", show_alert=True)
    ginfo = groups_data.get(gk)
    if not ginfo:
        return await cb.answer("Нет такой группы!", show_alert=True)

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

    try:
        await update_group_message(bot, gk)
    except TelegramBadRequest:
        pass

    await send_financial_report(bot)
    await cb.answer("Оплата agent OK.")


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

    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow(
            "SELECT user_id FROM bookings WHERE group_key=$1 AND day=$2 AND time_slot=$3",
            gk, day, slot,
        )
        if not row:
            return await cb.answer(get_message(lang, "no_such_booking"), show_alert=True)
    finally:
        await db.db_pool.release(conn)

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
    else:  # agent
        await handle_agent_payment(cb, gk, day, slot, code)


@router.message(StateFilter(BookPaymentStates.waiting_for_amount), F.text)
async def process_payment_amount(message: Message, state: FSMContext):
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
    Обновляет сообщение в чате группы:
      • Текст: salary, cash и уже завершённые слоты (status ≠ 'booked')
      • Кнопки: только текущие «booked»-слоты
      • Между сегодня/завтра — неактивный разделитель
      • Сохраняет message_id в памяти и БД
    """
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    ginfo = groups_data[group_key]
    chat_id = ginfo["chat_id"]
    user_lang = "ru"  # или LANG_DEFAULT

    # 1) Формируем текст
    from utils.text_utils import format_html_pre
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"━━━━━━  🌹🌹 {group_key} 🌹🌹  ━━━━━━",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{get_message(user_lang,'salary')}: {ginfo.get('salary',0)}¥",
        f"{get_message(user_lang,'cash')}:   {ginfo.get('cash',0)}¥",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⏰ {get_message(user_lang,'booking_report')} ⏰",
    ]
    final = {'❌❌❌', '✅', '✅2', '✅✅', '✅✅✅'}
    for day in ("Сегодня","Завтра"):
        lines.append(f"\n{day}:")
        for slot in generate_time_slots():
            st = ginfo["time_slot_statuses"].get((day, slot))
            if st in final:
                uid = ginfo["slot_bookers"].get((day, slot))
                emoji = await get_user_language(uid) if uid else "?"
                lines.append(f"{slot} {st} {emoji}")

    text = format_html_pre("\n".join(lines))

    # 2) Удаляем старое сообщение
    old_id = ginfo.get("message_id")
    if old_id:
        try:
            await bot.delete_message(chat_id, old_id)
        except:
            pass

    # 3) Строим кнопки через билд
    builder = InlineKeyboardBuilder()
    for day in ("Сегодня","Завтра"):
        for slot in generate_time_slots():
            st = ginfo["time_slot_statuses"].get((day, slot))
            if st == "booked" or st is None:
                builder.button(
                    text=f"{day} {slot}",
                    callback_data=f"group_time|{group_key}|{day}|{slot}"
                )
        # разделитель между днями
        builder.button(text="──────────", callback_data="ignore")

    builder.adjust(1)
    kb = builder.as_markup()

    # 4) Отправляем новое сообщение и сохраняем ID
    msg = await bot.send_message(
        chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=kb
    )
    ginfo["message_id"] = msg.message_id

    # 5) Сохраняем в БД
    conn = await db.db_pool.acquire()
    try:
        await conn.execute(
            "UPDATE group_financial_data SET message_id=$1 WHERE group_key=$2",
            msg.message_id, group_key
        )
    finally:
        await db.db_pool.release(conn)

async def send_financial_report(bot: Bot):
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
    lines.append(f"━━━━ TOTAL (итog1 - балансы) = {total_final}¥ ━━━━")

    report = "<pre>" + "\n".join(lines) + "</pre>"
    try:
        await bot.send_message(FINANCIAL_REPORT_GROUP_ID, report, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка фин. отчёта: {e}")


@router.callback_query(F.data == "view_all_bookings", StateFilter("*"))
async def cmd_all(cb: CallbackQuery, state: FSMContext):
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


async def safe_delete_and_answer(msg: types.Message, text: str):
    try:
        await msg.delete()
    except:
        pass
    await msg.answer(text, parse_mode=ParseMode.HTML)
