# handlers/news.py
import json
import asyncio
import logging

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, InputMediaPhoto
)
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

import db
from handlers.language import get_user_language, get_message

logger = logging.getLogger(__name__)

from config import is_user_admin
class NewsStates(StatesGroup):
    waiting_for_photos = State()
    waiting_for_text = State()
    waiting_for_edit_text = State()

router = Router()

@router.message(Command("added"))
async def cmd_added(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if not is_user_admin(message.from_user.id):
        return await message.answer(get_message(lang, "no_permission"))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_message(lang, "btn_add"),    callback_data="news_add")],
        [InlineKeyboardButton(text=get_message(lang, "btn_edit"),   callback_data="news_edit")],
        [InlineKeyboardButton(text=get_message(lang, "btn_delete"), callback_data="news_delete")],
        [InlineKeyboardButton(text=get_message(lang, "btn_cancel"), callback_data="news_cancel")],
    ])
    msg = await message.answer(get_message(lang, "news_manage"), reply_markup=kb)
    await state.update_data(base_chat_id=msg.chat.id, base_message_id=msg.message_id)

@router.callback_query(F.data.in_(["news_add", "news_edit", "news_delete", "news_cancel"]))
async def process_news_action(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await callback.answer(get_message(lang, "no_permission"), show_alert=True)

    data = await state.get_data()
    base_chat_id = data.get("base_chat_id")
    base_msg_id = data.get("base_message_id")
    action = callback.data

    # Cancel all
    if action == "news_cancel":
        if base_chat_id and base_msg_id:
            try:
                await callback.message.bot.delete_message(base_chat_id, base_msg_id)
            except:
                pass
        await state.clear()
        return await callback.answer(get_message(lang, "cancelled"))

    # Delete
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

    # Edit
    if action == "news_edit":
        await callback.message.edit_text(get_message(lang, "news_edit_prompt"))
        await state.set_state(NewsStates.waiting_for_edit_text)
        return await callback.answer()

    # Add
    if action == "news_add":
        await state.update_data(file_ids=[])
        await callback.message.edit_text(get_message(lang, "news_photos_prompt"))
        await state.set_state(NewsStates.waiting_for_photos)
        return await callback.answer()


@router.message(StateFilter(NewsStates.waiting_for_photos), F.photo)
async def process_news_photos(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    file_ids = data.get("file_ids", [])
    if len(file_ids) >= 10:
        return await message.answer(get_message(lang, "news_photo_limit"))

    file_ids.append(message.photo[-1].file_id)
    await state.update_data(file_ids=file_ids)
    await message.answer(get_message(lang, "news_photo_received"))


@router.message(Command("done"), StateFilter(NewsStates.waiting_for_photos))
async def photos_done(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    file_ids = data.get("file_ids", [])
    if not file_ids:
        await message.answer(get_message(lang, "news_no_photos"))
        return await state.clear()

    base_chat_id = data.get("base_chat_id")
    base_msg_id = data.get("base_message_id")
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
    lang = await get_user_language(message.from_user.id)
    news_text = message.text.strip()
    data = await state.get_data()
    file_ids = data.get("file_ids", [])

    async with db.db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO news (file_ids, text) VALUES ($1, $2)",
            json.dumps(file_ids),
            news_text
        )

    await state.clear()
    await message.answer(get_message(lang, "news_saved"))


@router.message(StateFilter(NewsStates.waiting_for_edit_text), F.text)
async def process_edit_text(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
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
        await message.answer(
            get_message(lang, "news_item", id=row["id"], text=text_part)
        )
        files = json.loads(row["file_ids"] or "[]")
        if files:
            album = []
            for i, fid in enumerate(files[:10]):
                caption = get_message(lang, "news_photo") if i == 0 else None
                album.append(InputMediaPhoto(media=fid, caption=caption))
            await message.answer_media_group(album)

async def cmd_added(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        return await callback.answer("Нет прав", show_alert=True)
    await callback.message.answer("Здесь будут новости.")
