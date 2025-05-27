#handlers/startemoji.py

import os
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
    "😎","💃","👻","🤖","👑","🦁","❤️","💰","🥇","🍕","🦋","🐶","🐱","🦊","🦄",
    "🌟","🚀","🎉","🔥","⚡","💡","🌈","⭐","🎈","🍀",
    "🎶","📚","🎮","🏆","🥳","🚴","🏖️","🎁","🧩","📷"
]

@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    lang    = await get_user_language(user_id)

    if not db.db_pool:
        return await message.answer("БД не инициализирована!")

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT emoji FROM user_emojis WHERE user_id=$1", user_id)
        if row is None:
            await conn.execute(
                "INSERT INTO user_emojis (user_id, emoji) VALUES ($1, '')",
                user_id
            )
            emoji_val = ""
        else:
            emoji_val = row["emoji"]

    if emoji_val:
        await message.answer(get_message(lang, "emoji_assigned", emoji=emoji_val))
    else:
        await message.answer(get_message(lang, "emoji_missing"), parse_mode="HTML")
        await send_emoji_request_to_admins(user_id, bot)

async def send_emoji_request_to_admins(user_id: int, bot: Bot):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"Назначить эмоджи для {user_id}",
            callback_data=f"assign_emoji_{user_id}"
        )]
    ])
    for adm in map(int, os.getenv("ADMIN_IDS", "").split(",")):
        if not is_user_admin(adm):
            continue
        try:
            await bot.send_message(
                adm,
                f"Пользователь {user_id} ждёт присвоения эмоджи!",
                reply_markup=kb
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить админу {adm}: {e}")

@router.callback_query(F.data == "emoji")
async def emoji_via_button(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_user_admin(cb.from_user.id):
        await cb.answer("Только для админов!", show_alert=True)
        return
    await cmd_emoji(cb.message, bot, user_id=cb.from_user.id)
    await cb.answer()

@router.message(Command("emoji"))
async def cmd_emoji(message: Message, bot: Bot, user_id=None):
    user_id = user_id or message.from_user.id
    lang    = await get_user_language(user_id)

    if not is_user_admin(user_id):
        return await message.answer(get_message(lang, "admin_only"))

    if not db.db_pool:
        return await message.answer("db_pool == None!")

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, emoji FROM user_emojis ORDER BY user_id")

    if not rows:
        return await message.answer("Нет пользователей для назначения эмоджи.")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"ID={r['user_id']} [{r['emoji'] or '—'}]",
                callback_data=f"reassign_{r['user_id']}"
            )]
            for r in rows
        ]
    )
    await message.answer("Выберите пользователя:", reply_markup=kb)

@router.callback_query(F.data.startswith("assign_emoji_"))
async def callback_assign_emoji(callback: CallbackQuery, bot: Bot):
    if not is_user_admin(callback.from_user.id):
        return await callback.answer("Вы не админ!", show_alert=True)

    try:
        target_id = int(callback.data.split("_", 2)[2])
    except:
        return await callback.answer("Некорректный user_id!", show_alert=True)

    # строим клавиатуру эмоджи 5×7
    buttons, row = [], []
    for i, emo in enumerate(AVAILABLE_EMOJIS, start=1):
        row.append(InlineKeyboardButton(text=emo, callback_data=f"choose_emoji_{target_id}_{emo}"))
        if i % 5 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    try:
        await callback.message.edit_text(
            text=f"Выберите эмоджи для пользователя {target_id}:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()

@router.callback_query(F.data.startswith("choose_emoji_"))
async def callback_choose_emoji(callback: CallbackQuery, bot: Bot):
    if not is_user_admin(callback.from_user.id):
        return await callback.answer("Вы не админ!", show_alert=True)

    parts = callback.data.split("_", 2)[2]
    if "_" not in parts:
        return await callback.answer("Ошибка данных", show_alert=True)
    uid_str, emo = parts.split("_", 1)
    if not uid_str.isdigit():
        return await callback.answer("Некорректный user_id!", show_alert=True)
    target_id = int(uid_str)

    async with db.db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_emojis (user_id, emoji) VALUES ($1, $2)"
            " ON CONFLICT (user_id) DO UPDATE SET emoji = EXCLUDED.emoji",
            target_id, emo
        )

    try:
        await callback.message.edit_text(f"Пользователю {target_id} присвоен эмоджи: {emo}")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await callback.answer("Готово!")
    try:
        await bot.send_message(target_id, f"Вам назначен эмоджи: {emo}\nТеперь доступны все команды!")
    except Exception:
        pass  # Игнорируем ошибки отправки, если пользователь отключил бота или заблокировал
