# handlers/startemoji.py

import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import db
from config import is_user_admin, ADMIN_IDS
from handlers.language import get_user_language, get_message
from utils.bot_utils import safe_answer

logger = logging.getLogger(__name__)
router = Router()

STARTEMOJI_PHOTO = "photo/IMG_2585.JPG"

CUSTOM_EMOJIS = [
    "⚽️", "🪩", "🏀", "🏈", "⚾️", "🥎", "🎾", "🏐", "🏉", "🎱",
    "🏓", "🏸", "🥅", "⛳️", "🪁", "🏒", "🏑", "🏏", "🪃", "🥍",
    # ... добавь остальные по своему списку ...
]

TRIPLE_EMOJIS = ["⚽️", "🪩", "🏀"]  # изменяй по необходимости

class EmojiStates(StatesGroup):
    waiting_for_assign = State()

@router.message(Command("allemo"))
async def cmd_allemo(message: Message):
    user_id = message.from_user.id
    user_lang = await get_user_language(user_id)

    if not is_user_admin(user_id):
        return await safe_answer(
            message,
            get_message(user_lang, 'no_permission', default="Недостаточно прав.")
        )

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.user_id, u.username, e.emoji 
            FROM user_emojis e 
            JOIN users u ON e.user_id = u.user_id
        """)
    if not rows:
        return await safe_answer(message, "Нет пользователей с назначенными эмодзи.")

    text = "\n".join([
        f"{i+1}. {row['username'] or row['user_id']}: {row['emoji'] or '—'}"
        for i, row in enumerate(rows)
    ])
    await safe_answer(message, text)

@router.message(Command("emoji"))
async def cmd_emoji(message: Message, bot: Bot):
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    if not is_user_admin(user_id):
        return await safe_answer(
            message,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(lang, "admin_only", default="Только для админов."),
            show_alert=True
        )

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, username FROM users")
    if not rows:
        return await safe_answer(message, "Нет пользователей в базе.")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{row['username'] or row['user_id']}",
                callback_data=f"assign_emoji_{row['user_id']}"
            )] for row in rows
        ]
    )
    await safe_answer(
        message,
        photo=STARTEMOJI_PHOTO,
        caption="Выберите пользователя для назначения эмодзи:",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("assign_emoji_"))
async def assign_emoji_callback(callback: CallbackQuery, state: FSMContext):
    user_lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(user_lang, "admin_only", default="Только для админов."),
            show_alert=True
        )

    user_id = int(callback.data.removeprefix("assign_emoji_"))
    # Кнопки для одного эмодзи
    single_buttons = [
        InlineKeyboardButton(
            text=emoji,
            callback_data=f"choose_emoji_{user_id}_{emoji}"
        ) for emoji in CUSTOM_EMOJIS
    ]
    keyboard_rows = [single_buttons[i:i+5] for i in range(0, len(single_buttons), 5)]

    # Кнопка для тройки эмодзи
    triple_emojis_str = "".join(TRIPLE_EMOJIS)
    triple_btn = InlineKeyboardButton(
        text=triple_emojis_str,
        callback_data=f"assign_emojis_{user_id}_" + "_".join(TRIPLE_EMOJIS)
    )
    keyboard_rows.append([triple_btn])

    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=f"Выберите эмодзи (или тройку) для пользователя {user_id}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    )
    await state.set_state(EmojiStates.waiting_for_assign)

@router.callback_query(F.data.startswith("choose_emoji_"), EmojiStates.waiting_for_assign)
async def choose_emoji_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(user_lang, "admin_only", default="Только для админов."),
            show_alert=True
        )
    parts = callback.data.split("_")
    target_id = int(parts[2])
    emoji = parts[3]
    async with db.db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_emojis (user_id, emoji) VALUES ($1, $2) "
            "ON CONFLICT (user_id) DO UPDATE SET emoji = $2",
            target_id, emoji
        )
    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=f"Пользователю {target_id} назначен эмодзи: {emoji}"
    )
    try:
        await bot.send_message(
            target_id,
            f"Вам назначен эмодзи: {emoji}\nТеперь доступны все команды!"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение пользователю: {e}")
    await state.clear()

@router.callback_query(F.data.startswith("assign_emojis_"), EmojiStates.waiting_for_assign)
async def assign_multiple_emojis_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(user_lang, "admin_only", default="Только для админов."),
            show_alert=True
        )
    parts = callback.data.split("_")
    target_id = int(parts[2])
    assigned_emojis = parts[3:]
    emojis_str = ",".join(assigned_emojis)
    async with db.db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_emojis (user_id, emoji) VALUES ($1, $2) "
            "ON CONFLICT (user_id) DO UPDATE SET emoji = $2",
            target_id, emojis_str
        )
    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=f"Пользователю {target_id} назначены эмодзи: {''.join(assigned_emojis)}"
    )
    try:
        await bot.send_message(
            target_id,
            f"Вам назначены эмодзи: {''.join(assigned_emojis)}\nТеперь доступны все команды!"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение пользователю: {e}")
    await state.clear()

async def get_next_emoji(user_id: int) -> str:
    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT emoji FROM user_emojis WHERE user_id=$1", user_id)
    if row and row["emoji"]:
        emojis = row["emoji"].split(",")
        if len(emojis) > 1:
            next_emoji = emojis.pop(0)
            emojis.append(next_emoji)
            new_str = ",".join(emojis)
            async with db.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE user_emojis SET emoji=$1 WHERE user_id=$2",
                    new_str, user_id
                )
            return next_emoji
        else:
            return emojis[0]
    return "❓"

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username or f"{message.from_user.first_name} {message.from_user.last_name}"

    # Проверяем, есть ли эмодзи у пользователя
    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT emoji FROM user_emojis WHERE user_id=$1", user_id)
    if row and row["emoji"]:
        lang = await get_user_language(user_id)
        return await safe_answer(
            message,
            get_message(lang, 'start_success', default='Добро пожаловать! Эмодзи уже назначен.')
        )

    # Эмодзи ещё нет — отправить запрос админам
    lang = await get_user_language(user_id)
    text = f"Пользователь @{username} (ID: {user_id}) ожидает назначения эмодзи."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назначить эмодзи", callback_data=f"assign_emoji_{user_id}")]
    ])
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                text,
                reply_markup=kb
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить запрос админу: {e}")

    await safe_answer(
        message,
        get_message(lang, 'start_wait_approval', default='Ожидайте — ваш аккаунт отправлен на рассмотрение администратору.')
    )
