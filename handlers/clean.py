# handlers/clean.py

import logging
import os                                  # ← добавлено
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.types.input_file import FSInputFile   # ← добавлено
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

import db
from config import is_user_admin
from constants.booking_const import groups_data
from handlers.language import get_user_language, get_message
from handlers.booking.reporting import update_group_message
from handlers.states import CleanupStates

logger = logging.getLogger(__name__)
router = Router()

PHOTO_ID = "photo/IMG_2585.JPG"
last_bot_message: dict[int, int] = {}


async def safe_answer(entity, text: str | None = None, **kwargs):
    """
    Унифицированный ответ для сценария «Clean».
    Всегда удаляем предыдущую карточку-меню и отправляем новую с картинкой.
    """
    # ── 1. кому отвечаем
    if hasattr(entity, "message") and hasattr(entity.message, "chat"):
        chat_id = entity.message.chat.id
        bot = entity.message.bot
    else:                                      # CallbackQuery
        chat_id = entity.chat.id
        bot = entity.bot

    # ── 2. удалить предыдущее меню-сообщение (если есть)
    prev = last_bot_message.get(chat_id)
    if prev:
        try:
            await bot.delete_message(chat_id, prev)
        except TelegramBadRequest:
            pass

    # ── 3. подготовить фото-параметр
    photo: str | FSInputFile = PHOTO_ID
    if isinstance(photo, str) and os.path.exists(photo):      # ★ фикс
        photo = FSInputFile(photo)

    caption = text or kwargs.get("caption") or ""
    reply_markup = kwargs.get("reply_markup")

    # ── 4. отправить новое меню
    sent = await bot.send_photo(
        chat_id,
        photo=photo,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    last_bot_message[chat_id] = sent.message_id
    return sent

@router.message(Command("clean"))
@router.callback_query(F.data == "clean")
async def cmd_clean(entry: Message | CallbackQuery, state: FSMContext):
    user_id = entry.from_user.id
    lang    = await get_user_language(user_id)
    if not is_user_admin(user_id):
        txt = get_message(lang, "no_permission")
        return await safe_answer(entry, txt)

    # Удаление исходного сообщения (если вызвано кнопкой)
    if isinstance(entry, CallbackQuery):
        try:
            await entry.bot.delete_message(chat_id=entry.message.chat.id, message_id=entry.message.message_id)
        except:
            pass

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_message(lang, "clean_time"),   callback_data="clean_menu_time"),
            InlineKeyboardButton(text=get_message(lang, "clean_salary"), callback_data="clean_menu_salary"),
        ],
        [
            InlineKeyboardButton(text=get_message(lang, "clean_cash"),   callback_data="clean_menu_cash"),
            InlineKeyboardButton(text=get_message(lang, "clean_all"),    callback_data="clean_menu_all"),
        ],
    ])
    prompt = get_message(lang, "clean_prompt")
    await safe_answer(entry, prompt, reply_markup=kb)
    await state.update_data(base_chat_id=(entry.message.chat.id if hasattr(entry, 'message') else entry.chat.id))
    await state.set_state(CleanupStates.waiting_for_main_menu)

@router.callback_query(CleanupStates.waiting_for_main_menu, F.data.startswith("clean_menu_"))
async def process_clean_menu(cb: CallbackQuery, state: FSMContext):
    lang   = await get_user_language(cb.from_user.id)
    choice = cb.data.removeprefix("clean_menu_")

    if choice == "all":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_message(lang, "clean_confirm_all"), callback_data="confirm_all_all")],
            [InlineKeyboardButton(text=get_message(lang, "btn_cancel"),         callback_data="clean_cancel")],
        ])
        await safe_answer(cb, get_message(lang, "clean_confirm_all_prompt"), reply_markup=kb)
        await state.set_state(CleanupStates.waiting_for_confirmation)
        return

    label = get_message(lang, f"clean_{choice}")
    rows  = [[InlineKeyboardButton(text=get_message(lang, f"clean_all_{choice}"), callback_data=f"sect_all_{choice}")]]
    for grp in groups_data:
        rows.append([InlineKeyboardButton(text=grp, callback_data=f"sect_grp_{choice}_{grp}")])
    rows.append([InlineKeyboardButton(text=get_message(lang, "btn_cancel"), callback_data="clean_cancel")])

    await safe_answer(cb, get_message(lang, "clean_section_prompt", section=label), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await state.update_data(clean_section=choice)
    await state.set_state(CleanupStates.waiting_for_group_choice)

@router.callback_query(CleanupStates.waiting_for_confirmation, F.data.startswith("confirm_all_"))
async def confirm_all_section(cb: CallbackQuery, state: FSMContext):
    lang    = await get_user_language(cb.from_user.id)
    section = cb.data.removeprefix("confirm_all_")
    logger.info(f"[CLEAN] confirm all {section}")

    for grp in groups_data:
        groups_data[grp].update({
            'booked_slots': {'Сегодня':[], 'Завтра':[]},
            'unavailable_slots': {'Сегодня':set(), 'Завтра':set()},
            'time_slot_statuses': {},
            'slot_bookers': {},
            'salary': 0,
            'cash': 0,
        })
        if db.db_pool:
            async with db.db_pool.acquire() as conn:
                if section in ("time","all"):
                    await conn.execute("DELETE FROM bookings WHERE group_key=$1", grp)
                    await conn.execute("DELETE FROM group_time_slot_statuses WHERE group_key=$1", grp)
                if section in ("salary","all"):
                    await conn.execute("UPDATE group_financial_data SET salary=0 WHERE group_key=$1", grp)
                if section in ("cash","all"):
                    await conn.execute("UPDATE group_financial_data SET cash=0 WHERE group_key=$1", grp)
        await update_group_message(cb.bot, grp)

    await safe_answer(cb, get_message(lang, "clean_done_all", section=get_message(lang, f"clean_{section}")))
    await state.clear()

@router.callback_query(CleanupStates.waiting_for_group_choice, F.data.startswith("sect_grp_"))
async def process_section_group_choice(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    _, _, section, grp = cb.data.split("_",3)
    if grp not in groups_data:
        return await safe_answer(cb, get_message(lang, "no_such_group"), show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_message(lang, "clean_confirm_group"),
                              callback_data=f"confirm_grp_{section}_{grp}")],
        [InlineKeyboardButton(text=get_message(lang, "btn_cancel"), callback_data="clean_cancel")]
    ])
    await safe_answer(cb, get_message(lang, "clean_group_prompt", section=get_message(lang, f"clean_{section}"), group=grp),
                      reply_markup=kb)
    await state.set_state(CleanupStates.waiting_for_confirmation)

@router.callback_query(CleanupStates.waiting_for_confirmation, F.data.startswith("confirm_grp_"))
async def confirm_group_section(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    _, _, section, grp = cb.data.split("_",3)

    if section == "time":
        groups_data[grp].update({
            'booked_slots': {'Сегодня':[], 'Завтра':[]},
            'unavailable_slots': {'Сегодня':set(), 'Завтра':set()},
            'time_slot_statuses': {},
            'slot_bookers': {},
        })
        if db.db_pool:
            async with db.db_pool.acquire() as conn:
                await conn.execute("DELETE FROM bookings WHERE group_key=$1", grp)
                await conn.execute("DELETE FROM group_time_slot_statuses WHERE group_key=$1", grp)
    elif section == "salary":
        groups_data[grp]["salary"] = 0
        if db.db_pool:
            async with db.db_pool.acquire() as conn:
                await conn.execute("UPDATE group_financial_data SET salary=0 WHERE group_key=$1", grp)
    else:
        groups_data[grp]["cash"] = 0
        if db.db_pool:
            async with db.db_pool.acquire() as conn:
                await conn.execute("UPDATE group_financial_data SET cash=0 WHERE group_key=$1", grp)

    await update_group_message(cb.bot, grp)
    await safe_answer(cb, get_message(lang, "clean_done_group",
                                      section=get_message(lang, f"clean_{section}"),
                                      group=grp))
    await state.clear()

@router.callback_query(F.data == "clean_cancel")
async def process_clean_cancel(cb: CallbackQuery, state: FSMContext):
    lang = await get_user_language(cb.from_user.id)
    await safe_answer(cb, get_message(lang, "cancelled"))
    await state.clear()

@router.callback_query(F.data == "clean")
async def clean_via_button(cb: CallbackQuery, state: FSMContext):
    await cmd_clean(cb, state)
