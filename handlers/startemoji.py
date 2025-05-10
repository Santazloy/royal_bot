import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import db  # здесь db.db_pool будет использоваться
logger = logging.getLogger(__name__)

# Список админов (подставьте свои ID)
ADMIN_IDS = [7894353415, 7935161063, 1768520583]

# Набор доступных эмоджи
AVAILABLE_EMOJIS = [
    "😎", "💃", "👻", "🤖", "👑", "🦁", "❤️",
    "💰", "🥇", "🍕", "🦋", "🐶", "🐱", "🦊", "🦄"
]

router = Router()

def is_user_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    """
    /start — проверяем, есть ли уже назначенный эмоджи.
    Если нет, создаём запись и шлём запрос админам.
    """
    user_id = message.from_user.id

    # Убедимся, что db_pool не None
    if not db.db_pool:
        await message.answer("База данных не инициализирована (db_pool is None)!")
        return

    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT emoji FROM user_emojis WHERE user_id=$1",
            user_id
        )
        if row is None:
            # Создадим пустую запись
            await conn.execute(
                "INSERT INTO user_emojis (user_id, emoji) VALUES ($1, '')",
                user_id
            )
            emoji_val = ""
        else:
            emoji_val = row["emoji"] or ""

    if emoji_val:
        # Эмоджи уже есть
        await message.answer(
            f"Привет! У тебя уже есть эмоджи: {emoji_val}\n"
            "Можешь пользоваться всеми командами!"
        )
    else:
        # Нет эмоджи — сообщим пользователю и попросим админов назначить
        await message.answer(
            "У вас пока <b>нет</b> эмоджи.\n"
            "Дождитесь, пока администратор назначит вам эмоджи.\n\n"
            "До этого пользоваться командами нельзя, кроме /start.",
            parse_mode="HTML"
        )
        await send_emoji_request_to_admins(user_id, bot)

async def send_emoji_request_to_admins(user_id: int, bot: Bot):
    """
    Отправляем администраторам кнопку «Назначить эмоджи для XXX».
    """
    for admin_id in ADMIN_IDS:
        # Создаём клавиатуру с одной кнопкой
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"Назначить эмоджи для {user_id}",
                callback_data=f"assign_emoji_{user_id}"
            )
        ]])

        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"Пользователь {user_id} ждёт присвоения эмоджи!",
                reply_markup=kb
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить админу {admin_id}: {e}")

@router.callback_query(F.data.startswith("assign_emoji_"))
async def callback_assign_emoji(callback: CallbackQuery, bot: Bot):
    """
    Кнопка «Назначить эмоджи для {user_id}». Формируем клавиатуру с выбором эмоджи.
    """
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Вы не админ!", show_alert=True)
        return

    parts = callback.data.split("_", 2)  # ["assign", "emoji", "123456789"]
    if len(parts) < 3:
        await callback.answer("Некорректные данные!", show_alert=True)
        return

    user_id_str = parts[2]
    if not user_id_str.isdigit():
        await callback.answer("Некорректный user_id!", show_alert=True)
        return

    target_user_id = int(user_id_str)

    # Разбиваем эмоджи на ряды по 5
    row_size = 5
    inline_kb = []
    row_buf = []

    for i, emo in enumerate(AVAILABLE_EMOJIS, 1):
        cb = f"choose_emoji_{target_user_id}_{emo}"
        row_buf.append(InlineKeyboardButton(text=emo, callback_data=cb))
        if i % row_size == 0:
            inline_kb.append(row_buf)
            row_buf = []

    if row_buf:
        inline_kb.append(row_buf)

    kb = InlineKeyboardMarkup(inline_keyboard=inline_kb)

    await callback.message.edit_text(
        text=f"Выберите эмоджи для пользователя {target_user_id}:",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(F.data.startswith("choose_emoji_"))
async def callback_choose_emoji(callback: CallbackQuery, bot: Bot):
    """
    Когда админ нажимает на конкретный эмоджи из списка.
    """
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Вы не админ!", show_alert=True)
        return

    parts = callback.data.split("_", 2)  # ["choose", "emoji", "1234_😎"]
    if len(parts) != 3:
        await callback.answer("Ошибка формата!", show_alert=True)
        return

    sub = parts[2].split("_", 1)
    if len(sub) < 2:
        await callback.answer("Ошибка данных", show_alert=True)
        return

    user_id_str, chosen_emoji = sub
    if not user_id_str.isdigit():
        await callback.answer("Некорректный user_id!", show_alert=True)
        return

    target_user_id = int(user_id_str)

    if not db.db_pool:
        await callback.answer("db_pool is None!", show_alert=True)
        return

    # Сохраняем в таблицу user_emojis
    async with db.db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_emojis (user_id, emoji)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET emoji=excluded.emoji
            """,
            target_user_id,
            chosen_emoji
        )

    await callback.message.edit_text(
        text=f"Пользователю {target_user_id} присвоен эмоджи: {chosen_emoji}"
    )
    await callback.answer("Эмоджи назначен!")

    # Пытаемся уведомить самого пользователя
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=(
                f"Вам назначен эмоджи: {chosen_emoji}.\n"
                f"Теперь доступны все команды!"
            )
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить user_id={target_user_id}: {e}")

@router.message(Command("emoji"))
async def cmd_emoji(message: Message, bot: Bot):
    """
    /emoji — админ может менять эмоджи любому пользователю (список user_emojis).
    """
    if not is_user_admin(message.from_user.id):
        await message.answer("Только админ может менять эмоджи.")
        return

    if not db.db_pool:
        await message.answer("db_pool == None, нет подключения к БД!")
        return

    # Загружаем пользователей
    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, emoji FROM user_emojis ORDER BY user_id")

    if not rows:
        await message.answer("Нет пользователей в таблице user_emojis.")
        return

    # Делаем клавиатуру, каждая кнопка — отдельная строка
    inline_kb = []
    for row in rows:
        uid = row["user_id"]
        emj = row["emoji"] or "—"
        text_btn = f"ID={uid} [{emj}]"
        cb_data = f"reassign_{uid}"
        inline_kb.append([InlineKeyboardButton(text=text_btn, callback_data=cb_data)])

    kb = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await message.answer("Выберите пользователя:", reply_markup=kb)

@router.callback_query(F.data.startswith("reassign_"))
async def callback_reassign_emoji(callback: CallbackQuery, bot: Bot):
    """
    Когда админ нажимает на конкретного юзера, снова показываем полный список эмоджи.
    """
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Вы не админ!", show_alert=True)
        return

    user_str = callback.data.split("_", 1)[1]
    if not user_str.isdigit():
        await callback.answer("Некорректный user_id!", show_alert=True)
        return

    target_user_id = int(user_str)

    # Повторяем логику формирования списка AVAILABLE_EMOJIS
    row_size = 5
    inline_kb = []
    row_buf = []

    for i, emo in enumerate(AVAILABLE_EMOJIS, 1):
        cb = f"choose_emoji_{target_user_id}_{emo}"
        row_buf.append(InlineKeyboardButton(text=emo, callback_data=cb))
        if i % row_size == 0:
            inline_kb.append(row_buf)
            row_buf = []
    if row_buf:
        inline_kb.append(row_buf)

    kb = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    await callback.message.edit_text(
        text=f"Выберите новый эмоджи для пользователя {target_user_id}:",
        reply_markup=kb
    )
    await callback.answer()