import logging
from typing import List

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
]
TRIPLE_EMOJIS = ["⚽️", "🪩", "🏀"]

# ──────────────────── FSM ────────────────────
class EmojiStates(StatesGroup):
    waiting_for_assign = State()

# ──────────────────── helpers ─────────────────
async def _fetch_user_emojis(user_id: int) -> List[str]:
    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT emojis FROM user_emojis WHERE user_id=$1",
            user_id,
        )
    if not row or not row["emojis"]:
        return []
    return [e.strip() for e in row["emojis"].split(",") if e.strip()]

async def _save_user_emojis(user_id: int, emojis: List[str]) -> None:
    async with db.db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_emojis (user_id, emojis)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET emojis = EXCLUDED.emojis
            """,
            user_id,
            ",".join(emojis),
        )

# ──────────────────── /allemo ─────────────────
@router.message(Command("allemo"))
async def cmd_allemo(message: Message):
    uid  = message.from_user.id
    lang = await get_user_language(uid)

    if not is_user_admin(uid):
        return await safe_answer(
            message,
            get_message(lang, "no_permission", default="Недостаточно прав."),
        )

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.user_id, u.username, e.emojis
            FROM user_emojis e
            JOIN users u ON e.user_id = u.user_id
            """
        )
    if not rows:
        return await safe_answer(message, "Нет пользователей с назначенными эмодзи.")

    text = "\n".join(
        f"{i+1}. {row['username'] or row['user_id']}: {row['emojis'] or '—'}"
        for i, row in enumerate(rows)
    )
    await safe_answer(message, text)

# ──────────────────── /emoji ──────────────────
@router.message(Command("emoji"))
async def cmd_emoji(message: Message, bot: Bot):
    uid  = message.from_user.id
    lang = await get_user_language(uid)

    if not is_user_admin(uid):
        return await safe_answer(
            message,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(lang, "admin_only", default="Только для админов."),
            show_alert=True,
        )

    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, username FROM users")
    if not rows:
        return await safe_answer(message, "Нет пользователей в базе.")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=row["username"] or str(row["user_id"]),
                    callback_data=f"assign_emoji_{row['user_id']}",
                )
            ]
            for row in rows
        ]
    )
    await safe_answer(
        message,
        photo=STARTEMOJI_PHOTO,
        caption="Выберите пользователя для назначения эмодзи:",
        reply_markup=kb,
    )

# ───────────── выбор пользователя ─────────────
@router.callback_query(F.data.startswith("assign_emoji_"))
async def assign_emoji_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(lang, "admin_only", default="Только для админов."),
            show_alert=True,
        )

    target_id = int(callback.data.removeprefix("assign_emoji_"))

    single_buttons = [
        InlineKeyboardButton(text=e, callback_data=f"choose_emoji_{target_id}_{e}")
        for e in CUSTOM_EMOJIS
    ]
    rows = [single_buttons[i : i + 5] for i in range(0, len(single_buttons), 5)]
    rows.append(
        [
            InlineKeyboardButton(
                text="".join(TRIPLE_EMOJIS),
                callback_data=f"assign_emojis_{target_id}_{'_'.join(TRIPLE_EMOJIS)}",
            )
        ]
    )

    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=f"Выберите эмодзи (или тройку) для пользователя {target_id}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await state.set_state(EmojiStates.waiting_for_assign)

# ───────────── назначение одного ──────────────
@router.callback_query(F.data.startswith("choose_emoji_"), EmojiStates.waiting_for_assign)
async def choose_emoji_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(lang, "admin_only", default="Только для админов."),
            show_alert=True,
        )

    _, _, target_id_str, emoji = callback.data.split("_", 3)
    target_id = int(target_id_str)

    await _save_user_emojis(target_id, [emoji])

    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=f"Пользователю {target_id} назначен эмодзи: {emoji}",
    )
    try:
        await bot.send_message(target_id, f"Вам назначен эмодзи: {emoji}\nТеперь доступны все команды!")
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение пользователю: {e}")
    await state.clear()

# ───────────── назначение тройки ──────────────
@router.callback_query(F.data.startswith("assign_emojis_"), EmojiStates.waiting_for_assign)
async def assign_multiple_emojis_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(lang, "admin_only", default="Только для админов."),
            show_alert=True,
        )

    parts     = callback.data.split("_")
    target_id = int(parts[2])
    assigned  = parts[3:]

    await _save_user_emojis(target_id, assigned)

    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=f"Пользователю {target_id} назначены эмодзи: {''.join(assigned)}",
    )
    try:
        await bot.send_message(
            target_id, f"Вам назначены эмодзи: {''.join(assigned)}\nТеперь доступны все команды!"
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение пользователю: {e}")
    await state.clear()

# ───────────── next emoji для бэкэнда ─────────
async def get_next_emoji(user_id: int) -> str:
    emojis = await _fetch_user_emojis(user_id)
    if not emojis:
        await _save_user_emojis(user_id, ["👤"])
        return "👤"

    if len(emojis) == 1:
        return emojis[0]

    nxt = emojis.pop(0)
    emojis.append(nxt)
    await _save_user_emojis(user_id, emojis)
    return nxt

# ───────────────────── /start ──────────────────
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    user_id  = message.from_user.id
    username = message.from_user.username or message.from_user.full_name

    if await _fetch_user_emojis(user_id):
        lang = await get_user_language(user_id)
        return await safe_answer(
            message,
            get_message(lang, "start_success", default="Добро пожаловать! Эмодзи уже назначен."),
        )

    lang     = await get_user_language(user_id)
    req_text = f"Пользователь @{username} (ID: {user_id}) ожидает назначения эмодзи."
    kb       = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Назначить эмодзи", callback_data=f"assign_emoji_{user_id}")]]
    )
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, req_text, reply_markup=kb)
        except Exception as e:
            logger.warning(f"Не удалось отправить запрос админу: {e}")

    await safe_answer(
        message,
        get_message(
            lang,
            "start_wait_approval",
            default="Ожидайте — ваш аккаунт отправлен на рассмотрение администратору.",
        ),
    )
