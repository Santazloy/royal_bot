import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import db
from handlers.language import get_user_language, get_message
from config import is_user_admin

logger = logging.getLogger(__name__)
router = Router()

AVAILABLE_EMOJIS = [
    "😎", "💃", "👻", "🤖", "👑", "🦁", "❤️",
    "💰", "🥇", "🍕", "🦋", "🐶", "🐱", "🦊", "🦄"
]

@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    if not db.db_pool:
        await message.answer("База данных не инициализирована!")
        return

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT emoji FROM user_emojis WHERE user_id=$1", user_id)
        emoji_val = row["emoji"] if row else ""

        if row is None:
            await conn.execute("INSERT INTO user_emojis (user_id, emoji) VALUES ($1, '')", user_id)

    if emoji_val:
        await message.answer(get_message(lang, "emoji_assigned", emoji=emoji_val))
    else:
        await message.answer(get_message(lang, "emoji_missing"), parse_mode="HTML")
        await send_emoji_request_to_admins(user_id, bot)

async def send_emoji_request_to_admins(user_id: int, bot: Bot):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Назначить эмоджи для {user_id}", callback_data=f"assign_emoji_{user_id}")]
    ])
    known_admin_ids = [7894353415, 7935161063, 1768520583]  # используется централизованно

    for admin_id in known_admin_ids:
        if not is_user_admin(admin_id):
            continue
        try:
            await bot.send_message(
                admin_id,
                f"Пользователь {user_id} ждёт присвоения эмоджи!",
                reply_markup=kb
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить админу {admin_id}: {e}")

@router.callback_query(F.data.startswith("assign_emoji_"))
async def callback_assign_emoji(callback: CallbackQuery, bot: Bot):
    if not is_user_admin(callback.from_user.id):
        return await callback.answer("Вы не админ!", show_alert=True)

    try:
        target_user_id = int(callback.data.split("_", 2)[2])
    except (IndexError, ValueError):
        return await callback.answer("Некорректный user_id!", show_alert=True)

    row_size = 5
    inline_kb = []
    row_buf = []

    for i, emo in enumerate(AVAILABLE_EMOJIS, start=1):
        cb_data = f"choose_emoji_{target_user_id}_{emo}"
        row_buf.append(InlineKeyboardButton(text=emo, callback_data=cb_data))
        if i % row_size == 0:
            inline_kb.append(row_buf)
            row_buf = []
    if row_buf:
        inline_kb.append(row_buf)

    kb = InlineKeyboardMarkup(inline_keyboard=inline_kb)

    try:
        await callback.message.edit_text(
            text=f"Выберите эмоджи для пользователя {target_user_id}:",
            reply_markup=kb
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()

@router.callback_query(F.data.startswith("choose_emoji_"))
async def callback_choose_emoji(callback: CallbackQuery, bot: Bot):
    if not is_user_admin(callback.from_user.id):
        return await callback.answer("Вы не админ!", show_alert=True)

    parts = callback.data.split("_", 2)
    if len(parts) != 3 or "_" not in parts[2]:
        return await callback.answer("Ошибка данных", show_alert=True)

    user_id_str, chosen_emoji = parts[2].split("_", 1)
    if not user_id_str.isdigit():
        return await callback.answer("Некорректный user_id!", show_alert=True)

    target_user_id = int(user_id_str)
    if not db.db_pool:
        return await callback.answer("db_pool is None!", show_alert=True)

    async with db.db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_emojis (user_id, emoji)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET emoji=excluded.emoji
            """,
            target_user_id, chosen_emoji
        )

    try:
        await callback.message.edit_text(f"Пользователю {target_user_id} присвоен эмоджи: {chosen_emoji}")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await callback.answer("Эмоджи назначен!")
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=f"Вам назначен эмоджи: {chosen_emoji}.\nТеперь доступны все команды!"
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить user_id={target_user_id}: {e}")

@router.message(Command("emoji"))
async def cmd_emoji(message: Message, bot: Bot):
    if not is_user_admin(message.from_user.id):
        return await message.answer("Только админ может менять эмоджи.")

    if not db.db_pool:
        return await message.answer("db_pool == None, нет подключения к БД!")

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, emoji FROM user_emojis ORDER BY user_id")

    if not rows:
        return await message.answer("Нет пользователей в таблице user_emojis.")

    inline_kb = [
        [
            InlineKeyboardButton(
                text=f"ID={row['user_id']} [{row['emoji'] or '—'}]",
                callback_data=f"reassign_{row['user_id']}"
            )
        ] for row in rows
    ]

    await message.answer("Выберите пользователя:", reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb))

@router.callback_query(F.data.startswith("reassign_"))
async def callback_reassign_emoji(callback: CallbackQuery, bot: Bot):
    if not is_user_admin(callback.from_user.id):
        return await callback.answer("Вы не админ!", show_alert=True)

    user_str = callback.data.split("_", 1)[1]
    if not user_str.isdigit():
        return await callback.answer("Некорректный user_id!", show_alert=True)

    target_user_id = int(user_str)
    row_size = 5
    inline_kb = []
    row_buf = []

    for i, emo in enumerate(AVAILABLE_EMOJIS, start=1):
        cb = f"choose_emoji_{target_user_id}_{emo}"
        row_buf.append(InlineKeyboardButton(text=emo, callback_data=cb))
        if i % row_size == 0:
            inline_kb.append(row_buf)
            row_buf = []
    if row_buf:
        inline_kb.append(row_buf)

    kb = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    try:
        await callback.message.edit_text(
            text=f"Выберите новый эмоджи для пользователя {target_user_id}:",
            reply_markup=kb
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()
