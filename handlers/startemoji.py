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
from config import is_user_admin
from handlers.language import get_user_language, get_message
from utils.bot_utils import safe_answer  # единая функция отправки + удаления прошлых сообщений

logger = logging.getLogger(__name__)
router = Router()

# Вынесём file_id картинки, которая будет везде
STARTEMOJI_PHOTO = "AgACAgUAAyEFAASVOrsCAAIDEGg23brrLiadZoeFJf_tyxhHjaDIAALjzDEbHWu4VZUmEXsg9M7tAQADAgADeQADNgQ"

class EmojiStates(StatesGroup):
    waiting_for_emoji = State()

# Список доступных эмодзи
AVAILABLE_EMOJIS = [
    "😀","😃","😄","😁","😆","😅","😂","🤣","😊","😇",
    "😉","😌","😍","🥰","😘","😗","😙","😚","😋","😛",
    "😝","😜","🤪","🤨","🧐","🤓","😎","🥳","😏","😶",
    # … добавить остальные по необходимости
]

@router.message(Command("emoji"))
async def cmd_emoji(message: Message, bot: Bot, user_id: int = None):
    """
    Админ вызывает /emoji — бот присылает меню выбора пользователя.
    """
    user_id = user_id or message.from_user.id
    lang = await get_user_language(user_id)

    if not is_user_admin(user_id):
        return await safe_answer(
            message,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(lang, "admin_only"),
            show_alert=True
        )
    if not db.db_pool:
        return await safe_answer(
            message,
            photo=STARTEMOJI_PHOTO,
            caption="DB pool not initialized!"
        )

    # Считываем всех пользователей и их эмодзи
    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, emoji FROM user_emojis ORDER BY user_id")

    if not rows:
        return await safe_answer(
            message,
            photo=STARTEMOJI_PHOTO,
            caption="Нет пользователей для назначения эмоджи."
        )

    # Строим клавиатуру: одна кнопка на пользователя
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"ID={r['user_id']} [{r['emoji'] or '—'}]",
                callback_data=f"reassign_{r['user_id']}"
            )
        ]
        for r in rows
    ])

    # Отправляем меню с фото
    await safe_answer(
        message,
        photo=STARTEMOJI_PHOTO,
        caption="Выберите пользователя:",
        reply_markup=kb
    )

@router.callback_query(F.data == "emoji")
async def emoji_via_button(cb: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Тот же самый /emoji, но вызван из админ-меню кнопкой.
    """
    await cmd_emoji(cb.message, bot, user_id=cb.from_user.id)
    await cb.answer()

@router.callback_query(F.data.startswith("reassign_"))
async def callback_assign_emoji(callback: CallbackQuery, state: FSMContext):
    """
    Админ нажал на ID=user — показываем клавиатуру с эмодзи.
    """
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(lang, "admin_only"),
            show_alert=True
        )

    user_id_str = callback.data.removeprefix("reassign_")
    if not user_id_str.isdigit():
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption="Некорректный user_id!",
            show_alert=True
        )
    target_id = int(user_id_str)

    # Строим клавиатуру 5×?
    buttons = []
    row = []
    for i, emo in enumerate(AVAILABLE_EMOJIS, start=1):
        row.append(
            InlineKeyboardButton(
                text=emo,
                callback_data=f"choose_emoji_{target_id}_{emo}"
            )
        )
        if i % 5 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=f"Выберите эмоджи для пользователя {target_id}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("choose_emoji_"))
async def callback_choose_emoji(callback: CallbackQuery, bot: Bot):
    """
    Админ выбрал конкретное эмоджи — сохраняем в БД и уведомляем.
    """
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(lang, "admin_only"),
            show_alert=True
        )

    parts = callback.data.removeprefix("choose_emoji_")
    if "_" not in parts:
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption="Ошибка данных",
            show_alert=True
        )
    uid_str, emo = parts.split("_", 1)
    if not uid_str.isdigit():
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption="Некорректный user_id!",
            show_alert=True
        )
    target_id = int(uid_str)

    # Обновляем БД
    async with db.db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_emojis (user_id, emoji) VALUES ($1, $2) "
            "ON CONFLICT (user_id) DO UPDATE SET emoji = EXCLUDED.emoji",
            target_id, emo
        )

    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=f"Пользователю {target_id} присвоен эмоджи: {emo}"
    )

    # Уведомляем пользователя (если возможно)
    try:
        await bot.send_message(
            target_id,
            f"Вам назначен эмоджи: {emo}\nТеперь доступны все команды!"
        )
    except:
        pass

    await callback.answer()
