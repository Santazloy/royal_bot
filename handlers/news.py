# handlers/news.py

import json
import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.filters.command import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

import db
from handlers.language import get_user_language, get_message
from config import is_user_admin

logger = logging.getLogger(__name__)
router = Router()


class NewsStates(StatesGroup):
    waiting_for_photos    = State()
    waiting_for_text      = State()
    waiting_for_edit_text = State()


@router.message(Command("added"))
async def cmd_added(entry: Message | CallbackQuery, state: FSMContext):
    # Поддержка вызова из меню и из команды
    if isinstance(entry, CallbackQuery):
        user_id = entry.from_user.id
        send_fn = entry.message.answer
        finish  = entry.answer
    else:
        user_id = entry.from_user.id
        send_fn = entry.answer
        finish  = None

    lang = await get_user_language(user_id)
    if not is_user_admin(user_id):
        text = get_message(lang, "no_permission")
        if finish:
            return await finish(text, show_alert=True)
        return await send_fn(text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_message(lang, "btn_add"),    callback_data="news_add")],
        [InlineKeyboardButton(text=get_message(lang, "btn_edit"),   callback_data="news_edit")],
        [InlineKeyboardButton(text=get_message(lang, "btn_delete"), callback_data="news_delete")],
        [InlineKeyboardButton(text=get_message(lang, "btn_cancel"), callback_data="news_cancel")],
    ])
    prompt = get_message(lang, "news_manage")
    msg    = await send_fn(prompt, reply_markup=kb)
    await state.update_data(base_chat_id=msg.chat.id, base_message_id=msg.message_id)
    if finish:
        await finish()


@router.callback_query(F.data.in_(["news_add", "news_edit", "news_delete", "news_cancel"]))
async def process_news_action(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await callback.answer(get_message(lang, "no_permission"), show_alert=True)

    data         = await state.get_data()
    base_chat_id = data.get("base_chat_id")
    base_msg_id  = data.get("base_message_id")
    action       = callback.data

    # cancel
    if action == "news_cancel":
        if base_chat_id and base_msg_id:
            try:
                await callback.message.bot.delete_message(base_chat_id, base_msg_id)
            except:
                pass
        await state.clear()
        return await callback.answer(get_message(lang, "cancelled"))

    # delete all
    if action == "news_delete":
        async with db.db_pool.acquire() as conn:
            await conn.execute("DELETE FROM news")
        await callback.message.edit_text(get_message(lang, "news_deleted_all"))
        await asyncio.sleep(2)
        if base_chat_id and base_msg_id:
            try:
                await callback.message.bot.delete_message(base_chat_id, base_msg_id)
            except:
                pass
        await state.clear()
        return await callback.answer(get_message(lang, "done"))

    # edit text
    if action == "news_edit":
        await callback.message.edit_text(get_message(lang, "news_edit_prompt"))
        await state.set_state(NewsStates.waiting_for_edit_text)
        return await callback.answer()

    # add photos
    if action == "news_add":
        await state.update_data(file_ids=[])
        await callback.message.edit_text(get_message(lang, "news_photos_prompt"))
        await state.set_state(NewsStates.waiting_for_photos)
        return await callback.answer()


@router.message(StateFilter(NewsStates.waiting_for_photos), F.photo)
async def process_news_photos(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    files = data.get("file_ids", [])
    if len(files) >= 10:
        return await message.answer(get_message(lang, "news_photo_limit"))
    files.append(message.photo[-1].file_id)
    await state.update_data(file_ids=files)
    await message.answer(get_message(lang, "news_photo_received"))


@router.message(Command("done"), StateFilter(NewsStates.waiting_for_photos))
async def photos_done(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    files = data.get("file_ids", [])
    if not files:
        await message.answer(get_message(lang, "news_no_photos"))
        return await state.clear()

    base_chat_id = data.get("base_chat_id")
    base_msg_id  = data.get("base_message_id")
    if base_chat_id and base_msg_id:
        try:
            await message.bot.edit_message_text(
                text=get_message(lang, "news_photos_saved"),
                chat_id=base_chat_id,
                message_id=base_msg_id
            )
        except TelegramBadRequest:
            pass
    await state.set_state(NewsStates.waiting_for_text)


@router.message(StateFilter(NewsStates.waiting_for_text), F.text)
async def process_news_text(message: Message, state: FSMContext):
    lang      = await get_user_language(message.from_user.id)
    news_text = message.text.strip()
    data      = await state.get_data()
    files     = data.get("file_ids", [])

    async with db.db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO news (file_ids, text) VALUES ($1, $2)",
            json.dumps(files),
            news_text
        )
    await state.clear()
    await message.answer(get_message(lang, "news_saved"))


@router.message(StateFilter(NewsStates.waiting_for_edit_text), F.text)
async def process_edit_text(message: Message, state: FSMContext):
    lang     = await get_user_language(message.from_user.id)
    new_text = message.text.strip()
    async with db.db_pool.acquire() as conn:
        await conn.execute("UPDATE news SET text=$1 WHERE id=1", new_text)
    await state.clear()
    await message.answer(get_message(lang, "news_updated"))


@router.message(Command("news"))
async def cmd_show_news(message: Message):
    lang = await get_user_language(message.from_user.id)
    if db.db_pool is None:
        return await message.answer(get_message(lang, "db_not_initialized"))

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, file_ids, text FROM news ORDER BY id DESC")
    if not rows:
        return await message.answer(get_message(lang, "news_none"))

    for row in rows:
        text_part = row["text"] or get_message(lang, "news_no_text")
        await message.answer(get_message(lang, "news_item", id=row["id"], text=text_part))
        files = json.loads(row["file_ids"] or "[]")
        if files:
            media = [
                InputMediaPhoto(media=fid, caption=(get_message(lang, "news_photo") if i == 0 else None))
                for i, fid in enumerate(files[:10])
            ]
            await message.answer_media_group(media)


@router.callback_query(F.data == "added")
async def added_via_button(cb: CallbackQuery, state: FSMContext):
    await cmd_added(cb, state)
    await cb.answer()
