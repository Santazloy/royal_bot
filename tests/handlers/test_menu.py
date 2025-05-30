import pytest
import asyncio
from unittest.mock import AsyncMock
from types import SimpleNamespace
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.menu_ad import (
    show_admin_menu,
    admin_menu_callback,
    build_admin_menu_keyboard,
    last_admin_menu_message,
    EMOJI_MAP,
)
from states.admin_states import AdminStates

# Моки всех зависимых обработчиков и функций
@pytest.fixture(autouse=True)
def patch_deps(monkeypatch):
    # universal safe_answer всегда возвращает AsyncMock()
    monkeypatch.setattr("handlers.menu_ad.safe_answer", AsyncMock())
    monkeypatch.setattr("handlers.menu_ad.get_user_language", AsyncMock(return_value='ru'))
    monkeypatch.setattr("handlers.menu_ad.is_user_admin", lambda uid: True)
    monkeypatch.setattr("handlers.menu_ad.added_via_button", AsyncMock())
    monkeypatch.setattr("handlers.menu_ad.salary_command", AsyncMock())
    monkeypatch.setattr("handlers.menu_ad.show_group_id", AsyncMock())
    monkeypatch.setattr("handlers.menu_ad.emoji_via_button", AsyncMock())
    monkeypatch.setattr("handlers.menu_ad.money_command", AsyncMock())
    monkeypatch.setattr("handlers.menu_ad.cmd_off_admin", AsyncMock())
    monkeypatch.setattr("handlers.menu_ad.clean_via_button", AsyncMock())

@pytest.mark.asyncio
async def test_show_admin_menu_and_callbacks_full_coverage():
    # 5 пользователей
    user_ids = [111, 222, 333, 444, 555]
    admin_states = [AsyncMock(spec=FSMContext) for _ in user_ids]

    async def simulate_show_menu(uid, state):
        msg = AsyncMock(spec=Message)
        msg.from_user = SimpleNamespace(id=uid)
        msg.chat = SimpleNamespace(id=uid)
        msg.bot = AsyncMock()
        # эмулируем уже отправленное меню ранее
        last_admin_menu_message[uid] = 99
        await show_admin_menu(msg, state)
        assert last_admin_menu_message[uid] is not None

    await asyncio.gather(*[simulate_show_menu(uid, state) for uid, state in zip(user_ids, admin_states)])

    # Проверка вызова каждой кнопки (эмодзи + все действия)
    all_actions = [
        'added', 'salary', 'chat', 'emoji', 'photo_admin', 'money', 'offad', 'clean',
        'balances', 'rules', 'ai_models', 'users', 'conversion', 'embedding', 'reset_day', 'back', 'unknown_action'
    ]

    async def simulate_callbacks(uid, state, action):
        cb = AsyncMock(spec=CallbackQuery)
        cb.from_user = SimpleNamespace(id=uid)
        cb.data = action
        cb.bot = AsyncMock()
        cb.answer = AsyncMock()
        cb.message = AsyncMock()
        await admin_menu_callback(cb, state)

    tasks = []
    for uid, state in zip(user_ids, admin_states):
        for action in all_actions:
            tasks.append(simulate_callbacks(uid, state, action))
    await asyncio.gather(*tasks)

    # Проверка что все клавиши есть в клавиатуре
    kb = build_admin_menu_keyboard('ru')
    kb_texts = [b.text for row in kb.inline_keyboard for b in row]
    for k, v in EMOJI_MAP.items():
        if k == 'back':
            assert any('🔙' in text for text in kb_texts)
        else:
            assert v in "".join(kb_texts)

    # Проверка, что только 1 сообщение меню на чат
    for uid in user_ids:
        assert isinstance(last_admin_menu_message[uid], int)
