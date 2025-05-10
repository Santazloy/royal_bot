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

import db

logger = logging.getLogger(__name__)

def is_user_admin(user_id: int) -> bool:
    return user_id in [7894353415, 7935161063, 1768520583]

class NewsStates(StatesGroup):
    waiting_for_photos = State()
    waiting_for_text = State()
    waiting_for_edit_text = State()

router = Router()

@router.message(Command("added"))
async def cmd_added(message: Message, state: FSMContext):
    if not is_user_admin(message.from_user.id):
        await message.answer("У вас нет прав для управления новостями.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить", callback_data="news_add")],
        [InlineKeyboardButton(text="Редактировать", callback_data="news_edit")],
        [InlineKeyboardButton(text="Удалить", callback_data="news_delete")],
        [InlineKeyboardButton(text="Отменить", callback_data="news_cancel")]
    ])
    msg = await message.answer("Управление новостями:", reply_markup=kb)
    await state.update_data(base_chat_id=msg.chat.id, base_message_id=msg.message_id)

@router.callback_query(F.data.in_(["news_add", "news_edit", "news_delete", "news_cancel"]))
async def process_news_action(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Нет прав!", show_alert=True)
        return

    data = await state.get_data()
    base_chat_id = data.get("base_chat_id")
    base_msg_id = data.get("base_message_id")
    action = callback.data

    if action == "news_cancel":
        if base_chat_id and base_msg_id:
            try:
                await callback.message.bot.delete_message(base_chat_id, base_msg_id)
            except:
                pass
        await state.clear()
        await callback.answer("Отменено.")
        return

    if action == "news_delete":
        async with db.db_pool.acquire() as conn:
            await conn.execute("DELETE FROM news")
        await callback.message.edit_text("Все новости удалены.")
        await asyncio.sleep(2)
        if base_chat_id and base_msg_id:
            try:
                await callback.message.bot.delete_message(base_chat_id, base_msg_id)
            except:
                pass
        await state.clear()
        await callback.answer("Готово.")
        return

    if action == "news_edit":
        await callback.message.edit_text(
            "Редактирование (демо). Пришлите новый текст — обновим запись c id=1."
        )
        await state.set_state(NewsStates.waiting_for_edit_text)
        await callback.answer()
    elif action == "news_add":
        await state.update_data(file_ids=[])
        await callback.message.edit_text("Отправьте до 10 фотографий. После — /done")
        await state.set_state(NewsStates.waiting_for_photos)
        await callback.answer()

@router.message(StateFilter(NewsStates.waiting_for_photos), F.photo)
async def process_news_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    file_ids = data.get("file_ids", [])
    if len(file_ids) >= 10:
        await message.answer("Лимит 10 фото! Введите /done, чтобы завершить.")
        return
    file_ids.append(message.photo[-1].file_id)
    await state.update_data(file_ids=file_ids)
    await message.answer("Фото получено. Отправьте ещё или /done")

@router.message(Command("done"), StateFilter(NewsStates.waiting_for_photos))
async def photos_done(message: Message, state: FSMContext):
    data = await state.get_data()
    file_ids = data.get("file_ids", [])
    if not file_ids:
        await message.answer("Нет фото. /done отменено.")
        await state.clear()
        return

    await state.update_data(file_ids=file_ids)
    base_chat_id = data.get("base_chat_id")
    base_msg_id = data.get("base_message_id")

    if base_chat_id and base_msg_id:
        try:
            await message.bot.edit_message_text(
                text="Фотографии сохранены. Теперь отправьте текст новости:",
                chat_id=base_chat_id,
                message_id=base_msg_id
            )
        except:
            pass

    await state.set_state(NewsStates.waiting_for_text)

@router.message(StateFilter(NewsStates.waiting_for_text), F.text)
async def process_news_text(message: Message, state: FSMContext):
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
    await message.answer("Новости успешно сохранены!")

@router.message(StateFilter(NewsStates.waiting_for_edit_text), F.text)
async def process_edit_text(message: Message, state: FSMContext):
    new_text = message.text.strip()
    async with db.db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE news SET text=$1 WHERE id=1",
            new_text
        )
    await state.clear()
    await message.answer("Новость (id=1) обновлена!")

@router.message(Command("news"))
async def cmd_show_news(message: Message):
    if db.db_pool is None:
        await message.answer("db_pool == None, не инициализирован!")
        return

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, file_ids, text FROM news ORDER BY id DESC")

    if not rows:
        await message.answer("Пока нет новостей.")
        return

    for row in rows:
        text_part = row["text"] or "(без текста)"
        files = json.loads(row["file_ids"] or "[]")
        await message.answer(f"📰 ID={row['id']}: {text_part}")
        if files:
            album = []
            for i, fid in enumerate(files[:10]):
                if i == 0:
                    album.append(InputMediaPhoto(media=fid, caption="Фото"))
                else:
                    album.append(InputMediaPhoto(media=fid))
            await message.answer_media_group(album)