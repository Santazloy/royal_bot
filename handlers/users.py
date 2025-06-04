# handlers/users.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command

import db
from config import is_user_admin
from handlers.language import get_user_language, get_message
from handlers.states import UsersManagementStates

users_router = Router()


async def _send_users_list(send_func, admin_id: int, lang: str, state: FSMContext):
    """
    Выполнить SELECT всех пользователей из БД, собрать текст, показать кнопки “Новый пользователь / Удалить” и
    для каждого существующего user_id кнопку “Редактировать: <uid> (<username>)”.
    """
    conn = await db.db_pool.acquire()
    try:
        rows = await conn.fetch(
            """
            SELECT u.user_id, u.username, u.balance, e.emojis
            FROM users u
            LEFT JOIN user_emojis e ON u.user_id = e.user_id
            ORDER BY u.user_id
            """
        )
    finally:
        await db.db_pool.release(conn)

    if rows:
        lines = []
        for r in rows:
            uid = r["user_id"]
            uname = r["username"] or f"User {uid}"
            bal = r["balance"] or 0
            emojis_str = r["emojis"] or ""
            first_emoji = (
                (emojis_str.split(",")[0].strip() if "," in emojis_str else emojis_str.strip())
                or "👤"
            )
            lines.append(f"ID={uid}, {uname}, {first_emoji}, Баланс={bal}¥")
        text = "\n".join(lines)
    else:
        text = "Нет пользователей в БД."

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Новый пользователь", callback_data="users_new"),
                InlineKeyboardButton(text="Удалить", callback_data="users_delete"),
            ]
        ]
    )
    if rows:
        for r in rows:
            uid = r["user_id"]
            uname = r["username"] or f"User {uid}"
            cb_data = f"edit_user_{uid}"
            kb.inline_keyboard.append(
                [InlineKeyboardButton(text=f"Редактировать: {uid} ({uname})", callback_data=cb_data)]
            )

    await send_func(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=kb)
    await state.set_state(UsersManagementStates.waiting_for_user_selection)


@users_router.message(Command("users"))
async def cmd_users(message: Message, state: FSMContext):
    """
    /users — показать админам список всех пользователей + кнопки “Новый пользователь / Удалить” / “Edit” → переход
    в FSM
    """
    admin_id = message.from_user.id
    lang = await get_user_language(admin_id)
    if not is_user_admin(admin_id):
        await message.answer(get_message(lang, "no_permission"))
        return

    await _send_users_list(message.answer, admin_id, lang, state)


@users_router.callback_query(F.data == "users_new")
async def cb_users_new(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text("Введите numeric ID для нового пользователя:")
    await state.set_state(UsersManagementStates.waiting_for_new_user_id)


@users_router.message(F.state == UsersManagementStates.waiting_for_new_user_id)
async def process_input_new_user_id(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if not is_user_admin(admin_id):
        await message.answer("Нет прав")
        return

    input_str = message.text.strip()
    if not input_str.isdigit():
        await message.answer("Некорректный ввод, попробуйте ещё раз.")
        return

    new_id = int(input_str)
    conn = await db.db_pool.acquire()
    try:
        await conn.execute(
            """
            INSERT INTO users(user_id, username, balance)
            VALUES ($1, NULL, 0)
            ON CONFLICT (user_id) DO NOTHING
            """,
            new_id,
        )
        await conn.execute(
            """
            INSERT INTO user_emojis (user_id, emojis)
            VALUES ($1, '')
            ON CONFLICT (user_id) DO NOTHING
            """,
            new_id,
        )
    finally:
        await db.db_pool.release(conn)

    await message.answer(
        f"Пользователь {new_id} добавлен (имя и эмодзи пока не заданы)."
    )
    await state.clear()


@users_router.callback_query(F.data == "users_delete")
async def cb_users_delete(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    conn = await db.db_pool.acquire()
    try:
        rows = await conn.fetch("SELECT user_id, username FROM users ORDER BY user_id")
    finally:
        await db.db_pool.release(conn)

    if not rows:
        await callback.message.edit_text("Нет пользователей для удаления.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for r in rows:
        uid = r["user_id"]
        uname = r["username"] or f"User {uid}"
        kb.inline_keyboard.append(
            [InlineKeyboardButton(text=f"{uid} ({uname})", callback_data=f"delete_user_{uid}")]
        )

    await callback.message.edit_text("Выберите, кого удалить:", reply_markup=kb)
    await state.set_state(UsersManagementStates.waiting_for_delete_choice)


@users_router.callback_query(
    F.data.startswith("delete_user_"), UsersManagementStates.waiting_for_delete_choice
)
async def process_delete_user_choice(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    user_id_str = callback.data.split("delete_user_")[1]
    if not user_id_str.isdigit():
        await callback.message.edit_text("Некорректные данные.")
        await state.clear()
        return

    user_id_to_delete = int(user_id_str)
    conn = await db.db_pool.acquire()
    try:
        await conn.execute("DELETE FROM user_emojis WHERE user_id = $1", user_id_to_delete)
        await conn.execute("DELETE FROM users WHERE user_id = $1", user_id_to_delete)
    finally:
        await db.db_pool.release(conn)

    await callback.message.edit_text(f"Пользователь {user_id_to_delete} удалён.")
    await state.clear()


@users_router.callback_query(
    F.data.startswith("edit_user_"), UsersManagementStates.waiting_for_user_selection
)
async def cb_edit_user(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    user_id_str = callback.data.split("edit_user_")[1]
    if not user_id_str.isdigit():
        await callback.message.edit_text("Некорректные данные.")
        await state.clear()
        return

    target_user_id = int(user_id_str)
    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow(
            """
            SELECT u.user_id, u.username, u.balance, e.emojis
            FROM users u
            LEFT JOIN user_emojis e ON u.user_id = e.user_id
            WHERE u.user_id = $1
            """,
            target_user_id,
        )
    finally:
        await db.db_pool.release(conn)

    if not row:
        await callback.message.edit_text("Пользователь не найден.")
        await state.clear()
        return

    await state.update_data(edit_user_id=target_user_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Изм. имя", callback_data="edit_name"),
                InlineKeyboardButton(text="Изм. эмодзи", callback_data="edit_emoji"),
            ],
            [InlineKeyboardButton(text="Изм. баланс", callback_data="edit_balance")],
        ]
    )
    uname = row["username"] or f"User {row['user_id']}"
    emojis_str = row["emojis"] or ""
    bal = row["balance"] or 0

    await callback.message.edit_text(
        (
            f"Редактируем пользователя ID={target_user_id}\n\n"
            f"Имя: {uname}\n"
            f"Эмодзи: {emojis_str}\n"
            f"Баланс: {bal}¥\n\n"
            f"Выберите, что изменить:"
        ),
        reply_markup=kb,
    )
    await state.set_state(UsersManagementStates.waiting_for_edit_choice)


@users_router.callback_query(F.data == "edit_name", UsersManagementStates.waiting_for_edit_choice)
async def cb_edit_name(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text("Введите новое имя пользователя:")
    await state.set_state(UsersManagementStates.waiting_for_new_name)


@users_router.message(F.state == UsersManagementStates.waiting_for_new_name)
async def process_new_name(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if not is_user_admin(admin_id):
        await message.answer("Нет прав")
        return

    new_name = message.text.strip()
    data = await state.get_data()
    user_id_ = data.get("edit_user_id")
    if user_id_ is None:
        await message.answer("Нет выбранного пользователя.")
        await state.clear()
        return

    conn = await db.db_pool.acquire()
    try:
        await conn.execute(
            "UPDATE users SET username = $1 WHERE user_id = $2", new_name, user_id_
        )
    finally:
        await db.db_pool.release(conn)

    await message.answer(f"Имя пользователя {user_id_} обновлено: {new_name}")
    await state.clear()


@users_router.callback_query(F.data == "edit_emoji", UsersManagementStates.waiting_for_edit_choice)
async def cb_edit_emoji(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text("Введите новый эмодзи (или список через запятую):")
    await state.set_state(UsersManagementStates.waiting_for_new_emoji)


@users_router.message(F.state == UsersManagementStates.waiting_for_new_emoji)
async def process_new_emoji(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if not is_user_admin(admin_id):
        await message.answer("Нет прав")
        return

    new_emoji_str = message.text.strip()
    data = await state.get_data()
    user_id_ = data.get("edit_user_id")
    if user_id_ is None:
        await message.answer("Нет выбранного пользователя.")
        await state.clear()
        return

    conn = await db.db_pool.acquire()
    try:
        await conn.execute(
            """
            INSERT INTO user_emojis (user_id, emojis)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET emojis = EXCLUDED.emojis
            """,
            user_id_,
            new_emoji_str,
        )
    finally:
        await db.db_pool.release(conn)

    await message.answer(f"Эмодзи для {user_id_} обновлено: {new_emoji_str}")
    await state.clear()


@users_router.callback_query(F.data == "edit_balance", UsersManagementStates.waiting_for_edit_choice)
async def cb_edit_balance(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+", callback_data="editbal_plus"),
                InlineKeyboardButton(text="-", callback_data="editbal_minus"),
            ]
        ]
    )
    await callback.answer()
    await callback.message.edit_text("Изменение баланса: выберите операцию:", reply_markup=kb)
    await state.set_state(UsersManagementStates.waiting_for_balance_op)


@users_router.callback_query(
    F.data.startswith("editbal_"), UsersManagementStates.waiting_for_balance_op
)
async def cb_editbal_op(callback: CallbackQuery, state: FSMContext):
    if not is_user_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return

    op_str = callback.data.split("editbal_")[1]
    await callback.answer()
    if op_str not in ("plus", "minus"):
        await callback.message.edit_text("Некорректные данные.")
        await state.clear()
        return

    await state.update_data(balance_op=op_str)
    await callback.message.edit_text("Введите сумму (число):")
    await state.set_state(UsersManagementStates.waiting_for_balance_value)


@users_router.message(F.state == UsersManagementStates.waiting_for_balance_value)
async def process_balance_value(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if not is_user_admin(admin_id):
        await message.answer("Нет прав")
        return

    val_str = message.text.strip()
    if not val_str.isdigit():
        await message.answer("Нужно ввести число. /cancel для отмены.")
        return

    amount = int(val_str)
    if amount <= 0:
        await message.answer("Сумма должна быть > 0.")
        return

    data = await state.get_data()
    user_id_ = data.get("edit_user_id")
    op = data.get("balance_op")
    if user_id_ is None or op not in ("plus", "minus"):
        await message.answer("Некорректные данные.")
        await state.clear()
        return

    delta = amount if op == "plus" else -amount

    conn = await db.db_pool.acquire()
    try:
        row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id_)
        if not row:
            await message.answer("Пользователь не найден в таблице users.")
            await state.clear()
            return

        new_balance = (row["balance"] or 0) + delta
        await conn.execute("UPDATE users SET balance = $1 WHERE user_id = $2", new_balance, user_id_)
    finally:
        await db.db_pool.release(conn)

    op_text = "+" if op == "plus" else "-"
    await message.answer(
        f"Баланс пользователя {user_id_} изменён ({op_text}{amount}), итог: {new_balance}¥"
    )
    await state.clear()


@users_router.callback_query(F.data == "balances")
async def show_users_via_callback(callback: CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    if not is_user_admin(callback.from_user.id):
        await callback.answer(get_message(lang, "no_permission"), show_alert=True)
        return

    await callback.answer()
    await _send_users_list(callback.message.answer, callback.from_user.id, lang, state)
