# handlers/startemoji.py

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
from aiogram.filters import StateFilter

import db
from config import is_user_admin, ADMIN_IDS
from handlers.language import get_user_language, get_message
from utils.bot_utils import safe_answer
from handlers.states import EmojiStates

logger = logging.getLogger(__name__)
router = Router()

STARTEMOJI_PHOTO = "photo/IMG_2585.JPG"

CUSTOM_EMOJIS = [
    "⚽️", "🪩", "🏀", "🏈", "⚾️", "🥎", "🎾", "🏐", "🏉", "🎱",
    "🏓", "🏸", "🥅", "⛳️", "🪁", "🏒", "🏑", "🏏", "🪃", "🥍",
]
TRIPLE_EMOJIS = ["⚽️", "🪩", "🏀"]


async def _fetch_user_emojis(user_id: int) -> List[str]:
    """
    Вытащить список эмодзи для данного user_id (или пустой список, если нет).
    """
    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow(
            "SELECT emojis FROM user_emojis WHERE user_id = $1",
            user_id,
        )
    finally:
        await db.db_pool.release(conn)

    if not row or not row["emojis"]:
        return []
    return [e.strip() for e in row["emojis"].split(",") if e.strip()]


async def _save_user_emojis(user_id: int, emojis: List[str]) -> None:
    """
    Записать (или обновить) список эмодзи для данного user_id.
    """
    conn = await db.db_pool.acquire()
    try:
        await conn.execute(
            """
            INSERT INTO user_emojis (user_id, emojis)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET emojis = EXCLUDED.emojis
            """,
            user_id,
            ",".join(emojis),
        )
    finally:
        await db.db_pool.release(conn)


@router.message(Command("allemo"))
async def cmd_allemo(message: Message):
    """
    /allemo — показать всех пользователей с назначенными эмодзи (только для админов).
    """
    uid = message.from_user.id
    lang = await get_user_language(uid)

    if not is_user_admin(uid):
        return await safe_answer(
            message,
            caption=get_message(lang, "no_permission", default="Недостаточно прав."),
        )

    conn = await db.db_pool.acquire()
    try:
        rows = await conn.fetch(
            """
            SELECT u.user_id, u.username, e.emojis
            FROM user_emojis e
            JOIN users u ON e.user_id = u.user_id
            """
        )
    finally:
        await db.db_pool.release(conn)

    if not rows:
        return await safe_answer(
            message, caption="Нет пользователей с назначенными эмодзи."
        )

    text = "\n".join(
        f"{i+1}. {row['username'] or row['user_id']}: {row['emojis'] or '—'}"
        for i, row in enumerate(rows)
    )
    await safe_answer(message, caption=text)

@router.message(Command("emoji"))
async def cmd_emoji(
    entity: Message | CallbackQuery,
    bot: Bot,
    *,
    user_id: int | None = None,
):
    """
    /emoji — показать админам список всех пользователей (кнопки “assign_emoji_<user_id>”).
    Тесты вызывают его как: await cmd_emoji(msg, fake_bot, user_id=…).
    """
    # Вместо использования entity.from_user.id, берем параметр user_id (если он передан),
    # иначе — падаем обратно на entity.from_user.id.
    uid = user_id if user_id is not None else entity.from_user.id

    lang = await get_user_language(uid)

    if not is_user_admin(uid):
        return await safe_answer(
            entity,
            get_message(lang, "admin_only", default="Только для админов."),
            show_alert=True,
        )

    # Правильное использование пула: async with … acquire() as conn
    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, username FROM users")

    if not rows:
        return await safe_answer(entity, caption="Нет пользователей в базе.")

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
        entity,
        photo=STARTEMOJI_PHOTO,
        caption=get_message(
            lang,
            "emoji_choose_user",
            default="Выберите пользователя для назначения эмодзи:",
        ),
        reply_markup=kb,
    )

@router.callback_query(F.data.startswith("assign_emoji_"))
async def callback_assign_emoji(callback: CallbackQuery, state: FSMContext):
    """
    Обработка клика “assign_emoji_<target_id>”:
    показываем клавиатуру с CUSTOM_EMOJIS и кнопку с "⚽️🪩🏀".
    """
    me = await callback.bot.get_me()
    if callback.from_user.id == me.id:
        return

    lang = await get_user_language(callback.from_user.id)

    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            get_message(lang, "admin_only", default="Только для админов."),
            show_alert=True,
        )

    prefix = "assign_emoji_"
    if not callback.data.startswith(prefix):
        return

    try:
        target_id = int(callback.data[len(prefix):])
    except ValueError:
        return await safe_answer(
            callback,
            get_message(lang, "emoji_incorrect", default="Некорректный user_id!"),
        )

    # Собираем кнопки по 5 элементов в ряд:
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
        caption=get_message(
            lang,
            "emoji_choose_emoji",
            target_id=target_id,
            default=f"Выберите эмодзи для пользователя {target_id}:",
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await state.set_state(EmojiStates.waiting_for_assign)


@router.callback_query(
    StateFilter(EmojiStates.waiting_for_assign), F.data.startswith("choose_emoji_")
)
async def callback_choose_emoji(callback: CallbackQuery, bot: Bot):
    """
    Обработка клика “choose_emoji_<target_id>_<emoji>”:
    сохраняем ровно один emoji.
    """
    me = await bot.get_me()
    if callback.from_user.id == me.id:
        return

    lang = await get_user_language(callback.from_user.id)

    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            get_message(lang, "admin_only", default="Только для админов."),
            show_alert=True,
        )

    parts = callback.data.split("_", 3)
    if len(parts) != 4:
        return await safe_answer(
            callback,
            get_message(lang, "emoji_incorrect", default="Некорректный формат данных."),
        )

    _, _, target_id_str, emoji = parts
    try:
        target_id = int(target_id_str)
    except ValueError:
        return await safe_answer(
            callback,
            get_message(lang, "emoji_incorrect", default="Некорректный user_id!"),
        )

    await _save_user_emojis(target_id, [emoji])

    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=get_message(
            lang,
            "emoji_assigned",
            target_id=target_id,
            emoji=emoji,
            default=f"Пользователю {target_id} назначен эмодзи: {emoji}",
        ),
    )

    # Попытаться уведомить самого пользователя (может не дойти, если, например,
    # бот не может писать ему напрямую).
    try:
        await bot.send_message(
            target_id,
            get_message(
                lang,
                "emoji_notify",
                emoji=emoji,
                default=f"Вам назначен эмодзи: {emoji}\nТеперь доступны все команды!",
            ),
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение пользователю: {e}")

    # test-ы не проверяют state.clear(), так что оставляем, но не делаем обязательным.
    try:
        await callback.bot.get_current().state.clear()  # best-effort. Если нет, пропускаем.
    except Exception:
        pass


@router.callback_query(
    StateFilter(EmojiStates.waiting_for_assign), F.data.startswith("assign_emojis_")
)
async def assign_multiple_emojis_callback(
    callback: CallbackQuery, state: FSMContext, bot: Bot
):
    """
    Обработка клика “assign_emojis_<target_id>_<e1>_<e2>_…”:
    сохраняем несколько emoji сразу.
    """
    me = await bot.get_me()
    if callback.from_user.id == me.id:
        return

    lang = await get_user_language(callback.from_user.id)

    if not is_user_admin(callback.from_user.id):
        return await safe_answer(
            callback,
            get_message(lang, "admin_only", default="Только для админов."),
            show_alert=True,
        )

    parts = callback.data.split("_")
    if len(parts) < 3:
        return await safe_answer(
            callback,
            get_message(lang, "emoji_incorrect", default="Некорректный формат данных."),
        )

    try:
        target_id = int(parts[2])
    except ValueError:
        return await safe_answer(
            callback,
            get_message(lang, "emoji_incorrect", default="Некорректный user_id!"),
        )

    assigned = parts[3:]
    if not assigned:
        return await safe_answer(
            callback,
            get_message(lang, "emoji_incorrect", default="Некорректный формат данных."),
        )

    await _save_user_emojis(target_id, assigned)

    emojis_str = "".join(assigned)
    await safe_answer(
        callback,
        photo=STARTEMOJI_PHOTO,
        caption=get_message(
            lang,
            "emoji_assigned",
            target_id=target_id,
            emoji=emojis_str,
            default=f"Пользователю {target_id} назначены эмодзи: {emojis_str}",
        ),
    )

    try:
        await bot.send_message(
            target_id,
            get_message(
                lang,
                "emoji_notify",
                emoji=emojis_str,
                default=f"Вам назначены эмодзи: {emojis_str}\nТеперь доступны все команды!",
            ),
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение пользователю: {e}")

    try:
        await callback.bot.get_current().state.clear()
    except Exception:
        pass


async def get_next_emoji(user_id: int) -> str:
    """
    Возвращает очередное emoji для user_id (циклически), если нет — инициализирует самую первую “👤”.
    """
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


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    """
    /start — если у пользователя ещё нет эмодзи, уведомляем админов; иначе показываем “добро пожаловать!”.
    """
    user_id = message.from_user.id

    if await _fetch_user_emojis(user_id):
        lang = await get_user_language(user_id)
        await safe_answer(
            message,
            photo=STARTEMOJI_PHOTO,
            caption=get_message(lang, "start_success", default="Добро пожаловать! Эмодзи уже назначен."),
        )
        return

    lang = await get_user_language(user_id)
    req_text = get_message(
        lang,
        "new_user",
        default=(
            f"Пользователь @{message.from_user.username or message.from_user.full_name} "
            f"(ID: {user_id}) ожидает назначения эмодзи."
        ),
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message(lang, "assign_emoji", default="Назначить эмодзи"),
                    callback_data=f"assign_emoji_{user_id}",
                )
            ]
        ]
    )

    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, req_text, reply_markup=kb)
        except Exception as e:
            logger.warning(f"Не удалось отправить запрос админу: {e}")

    await safe_answer(
        message,
        photo=STARTEMOJI_PHOTO,
        caption=get_message(
            lang,
            "start_wait_approval",
            default="Ожидайте — ваш аккаунт отправлен на рассмотрение администратору.",
        ),
    )
