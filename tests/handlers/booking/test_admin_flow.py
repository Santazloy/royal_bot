# tests/handlers/booking/test_admin_flow.py

import asyncio
import pytest

from aiogram import Bot
from aiogram.types import ChatMember, Chat, User, Message, CallbackQuery
from aiogram.enums import ChatMemberStatus

import handlers.booking.admin_flow as admin_flow_module
from constants.booking_const import status_mapping

# ─────────────────────────────────────────────────────────────────────────────
#                        Вспомогательные заглушки / утилиты
# ─────────────────────────────────────────────────────────────────────────────

class DummyMessage(Message):
    """
    Эмуляция aiogram.types.Message.
    Храним бот в приватном атрибуте _bot и возвращаем через свойство bot.
    Метод delete() помечает удаление.
    """
    def __init__(self, chat_id: int, bot: Bot):
        chat = Chat(id=chat_id, type="supergroup")
        from_user = User(id=0, is_bot=False, first_name="Dummy")
        super().__init__(
            message_id=1234,
            date=0,
            chat=chat,
            from_user=from_user,
            text=""
        )
        object.__setattr__(self, "_bot", bot)
        object.__setattr__(self, "_deleted", False)

    @property
    def bot(self) -> Bot:
        return getattr(self, "_bot")

    async def delete(self):
        object.__setattr__(self, "_deleted", True)


class DummyCallback(CallbackQuery):
    """
    Эмуляция aiogram.types.CallbackQuery.
    Переопределяем метод answer, чтобы принимать (text, show_alert).
    Переопределяем свойство bot, чтобы get_chat_member возвращал заглушку.
    """
    def __init__(self,
                 chat_id: int,
                 data: str,
                 bot: Bot,
                 user_id: int,
                 user_status: str = "administrator"):
        msg = DummyMessage(chat_id=chat_id, bot=bot)
        user = User(id=user_id, is_bot=False, first_name="TestUser")
        super().__init__(
            id="0",  # id должно быть строкой
            from_user=user,
            chat_instance="dummy_instance",
            message=msg,
            data=data
        )
        object.__setattr__(self, "_user_status", user_status)

    @property
    def bot(self):
        """
        Возвращаем «заглушечный» бот, у которого get_chat_member вызывает наш метод get_chat_member.
        """
        class _BotStub:
            def __init__(inner_self, parent_cb):
                object.__setattr__(inner_self, "_parent", parent_cb)

            async def get_chat_member(inner_self, chat_id, user_id):
                return await inner_self._parent.get_chat_member(chat_id, user_id)

            async def send_photo(inner_self, *args, **kwargs):
                """
                Если где-то внутри safe_answer всё-таки вызовется bot.send_photo,
                предотвратим настоящий HTTP-запрос.
                Просто вернём фейковый объект с message_id.
                """
                class FakeSent:
                    message_id = 777
                return FakeSent()

        return _BotStub(self)

    async def answer(self, text: str = None, show_alert: bool = False):
        # Заглушка, ничего не делает, но signature совпадает
        return

    async def get_chat_member(self, chat_id: int, user_id: int):
        """
        Возвращаем ChatMember с заданным статусом, используя сохранённый _user_status.
        """
        return ChatMember(
            user=User(id=user_id, is_bot=False, first_name="TestUser"),
            status=self._user_status,
            chat=Chat(id=chat_id, type="supergroup")
        )


class DummyDBConn:
    """Заглушка для подключения к БД, поддерживающая async context manager."""
    async def execute(self, *args, **kwargs):
        return

    async def fetchrow(self, *args, **kwargs):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyDBPool:
    """Заглушка для db.db_pool, чтобы работал `async with db.db_pool.acquire() as con:`"""
    def __init__(self):
        pass

    def __await__(self):
        # Иногда кто-то делает `await DummyDBPool()`, но мы никогда не выполняем этот путь.
        yield

    async def acquire(self):
        return DummyDBConn()


@pytest.fixture(autouse=True)
def patch_db_pool(monkeypatch):
    """
    Подменяем db.db_pool на DummyDBPool,
    чтобы не делать реальных запросов к базе.
    """
    import db
    monkeypatch.setattr(db, "db_pool", DummyDBPool())
    yield
    monkeypatch.setattr(db, "db_pool", None)


@pytest.fixture(autouse=True)
def clear_groups_data():
    """
    Очищаем и восстанавливаем groups_data перед каждым тестом.
    """
    original = admin_flow_module.groups_data.copy() if hasattr(admin_flow_module, "groups_data") else {}
    admin_flow_module.groups_data.clear()
    yield
    admin_flow_module.groups_data.clear()
    admin_flow_module.groups_data.update(original)


@pytest.fixture(autouse=True)
def patch_safe_answer(monkeypatch):
    """
    Подменяем функцию safe_answer в admin_flow_module и в utils.bot_utils,
    чтобы отслеживать её вызовы и предотвратить реальные HTTP-запросы.
    """
    calls = []

    async def fake_safe_answer(entity, *args, **kwargs):
        calls.append((entity, args, kwargs))
        class Sent:
            message_id = 999
        return Sent()

    # Перехватываем оба имени:
    monkeypatch.setattr(admin_flow_module, "safe_answer", fake_safe_answer)
    monkeypatch.setattr("utils.bot_utils.safe_answer", fake_safe_answer)
    return calls


@pytest.fixture(autouse=True)
def patch_update_group_message(monkeypatch):
    """
    Подменяем update_group_message, чтобы не посылать реальное сообщение.
    """
    calls = []

    async def fake_update_group_message(bot, group_key):
        calls.append(group_key)
        return

    monkeypatch.setattr(admin_flow_module, "update_group_message", fake_update_group_message)
    return calls


@pytest.fixture(autouse=True)
def patch_apply_special_user_reward(monkeypatch):
    """
    Подменяем apply_special_user_reward, чтобы не делать реальных вызовов.
    """
    calls = []

    async def fake_apply_special_user_reward(code, bot):
        calls.append(code)
        return

    monkeypatch.setattr(admin_flow_module, "apply_special_user_reward", fake_apply_special_user_reward)
    return calls


# ─────────────────────────────────────────────────────────────────────────────
#                     Тесты для admin_click_slot
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_click_slot_no_group(patch_safe_answer):
    """
    Если группа не существует в groups_data → cb.answer("Нет прав!", show_alert=True)
    safe_answer не вызывается.
    """
    bot = Bot(token="123456:TEST_TOKEN_IS_OK")
    cb = DummyCallback(
        chat_id=1,
        data="group_time|NON_EXISTENT|Сегодня|10:00",
        bot=bot,
        user_id=1
    )

    await admin_flow_module.admin_click_slot(cb)

    # safe_answer не должен быть вызван
    assert patch_safe_answer == []


@pytest.mark.asyncio
async def test_admin_click_slot_not_admin(patch_safe_answer):
    """
    Если группа есть, но пользователь не админ → cb.answer("Только админ!", show_alert=True)
    safe_answer не вызывается.
    """
    admin_flow_module.groups_data["G1"] = {
        "chat_id": 123,
        "slot_bookers": {},
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "time_slot_statuses": {}
    }

    bot = Bot(token="123456:TEST_TOKEN_IS_OK")
    cb = DummyCallback(
        chat_id=123,
        data="group_time|G1|Сегодня|10:00",
        bot=bot,
        user_id=1,
        user_status="member"
    )

    await admin_flow_module.admin_click_slot(cb)
    assert patch_safe_answer == []


@pytest.mark.asyncio
async def test_admin_click_slot_success(patch_safe_answer):
    """
    Корректный админ → удаляем старое сообщение, вызываем safe_answer с клавиатурой.
    """
    admin_flow_module.groups_data["G1"] = {
        "chat_id": 123,
        "slot_bookers": {("Сегодня", "10:00"): 42},
        "booked_slots": {"Сегодня": ["10:00"], "Завтра": []},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "time_slot_statuses": {("Сегодня", "10:00"): "booked"}
    }

    bot = Bot(token="123456:TEST_TOKEN_IS_OK")
    cb = DummyCallback(
        chat_id=123,
        data="group_time|G1|Сегодня|10:00",
        bot=bot,
        user_id=42,
        user_status="administrator"
    )

    await admin_flow_module.admin_click_slot(cb)

    # Один вызов safe_answer
    assert len(patch_safe_answer) == 1
    entity, args, kwargs = patch_safe_answer[0]
    assert entity == cb
    # Проверяем текст
    assert "<b>Выберите финальный статус слота:</b>" in args[0]
    # Проверяем фото
    assert kwargs.get("photo") == admin_flow_module.PHOTO_ID
    # Проверяем клавиатуру
    kb = kwargs.get("reply_markup")
    assert hasattr(kb, "inline_keyboard")

    # Динамически проверяем кнопки статусов (не более 3 в ряду) и одну кнопку в последнем ряду
    rows = kb.inline_keyboard
    # Последний ряд — кнопка отмены или возврата
    assert len(rows[-1]) == 1
    # Кнопки статусов располагаются в предыдущих рядах, не более 3 кнопок в ряду
    status_buttons = [btn for row in rows[:-1] for btn in row]
    assert len(status_buttons) == len(status_mapping)
    for row in rows[:-1]:
        assert 1 <= len(row) <= 3


@pytest.mark.asyncio
async def test_admin_click_slot_concurrent():
    """
    Проверяем одновременную обработку 10 запросов admin_click_slot разных админов.
    Все задачи должны завершиться без ошибок (None).
    """
    admin_flow_module.groups_data["G1"] = {
        "chat_id": 555,
        "slot_bookers": {("Сегодня", "10:00"): 1},
        "booked_slots": {"Сегодня": ["10:00"], "Завтра": []},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "time_slot_statuses": {("Сегодня", "10:00"): "booked"}
    }

    bot = Bot(token="123456:TEST_TOKEN_IS_OK")

    async def simulate(user_id):
        cb = DummyCallback(
            chat_id=555,
            data="group_time|G1|Сегодня|10:00",
            bot=bot,
            user_id=user_id,
            user_status="administrator"
        )
        return await admin_flow_module.admin_click_slot(cb)

    tasks = [simulate(uid) for uid in range(100, 110)]
    results = await asyncio.gather(*tasks)
    assert all(r is None for r in results)


# ─────────────────────────────────────────────────────────────────────────────
#                     Тесты для admin_click_status
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_click_status_no_group(patch_safe_answer):
    """
    Если группа не найдена → cb.answer("Нет прав!", show_alert=True)
    safe_answer не вызывается.
    """
    bot = Bot(token="123456:TEST_TOKEN_IS_OK")
    cb = DummyCallback(
        chat_id=10,
        data="group_status|NON_EXISTENT|Сегодня|10:00|1",
        bot=bot,
        user_id=1,
        user_status="administrator"
    )

    await admin_flow_module.admin_click_status(cb)
    assert patch_safe_answer == []


@pytest.mark.asyncio
async def test_admin_click_status_not_admin(patch_safe_answer):
    """
    Если пользователь не админ → cb.answer("Нет прав!", show_alert=True)
    safe_answer не вызывается.
    """
    admin_flow_module.groups_data["G1"] = {
        "chat_id": 20,
        "slot_bookers": {("Сегодня", "10:00"): 5},
        "booked_slots": {"Сегодня": ["10:00"], "Завтра": []},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "time_slot_statuses": {("Сегодня", "10:00"): "booked"}
    }

    bot = Bot(token="123456:TEST_TOKEN_IS_OK")
    cb = DummyCallback(
        chat_id=20,
        data="group_status|G1|Сегодня|10:00|1",
        bot=bot,
        user_id=5,
        user_status="member"
    )

    await admin_flow_module.admin_click_status(cb)
    assert patch_safe_answer == []


@pytest.mark.asyncio
async def test_admin_click_status_back(patch_safe_answer, patch_update_group_message):
    """
    Если code == "back" → вызывается update_group_message и cb.answer,
    safe_answer не вызывается.
    """
    admin_flow_module.groups_data["G1"] = {
        "chat_id": 30,
        "slot_bookers": {},
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "time_slot_statuses": {}
    }

    bot = Bot(token="123456:TEST_TOKEN_IS_OK")
    cb = DummyCallback(
        chat_id=30,
        data="group_status|G1|Сегодня|10:00|back",
        bot=bot,
        user_id=1,
        user_status="administrator"
    )

    await admin_flow_module.admin_click_status(cb)
    assert patch_update_group_message == ["G1"]
    assert patch_safe_answer == []


@pytest.mark.asyncio
async def test_admin_click_status_cancel_slot(patch_safe_answer, patch_update_group_message):
    """
    Если code == "-1" → удаление слота и соседних,
    update_group_message и safe_answer("Слот отменён.", photo).
    """
    admin_flow_module.groups_data["G1"] = {
        "chat_id": 40,
        "slot_bookers": {
            ("Сегодня", "10:00"): 7,
            ("Сегодня", "09:30"): 7,
            ("Сегодня", "10:30"): 7
        },
        "booked_slots": {"Сегодня": ["10:00"], "Завтра": []},
        "unavailable_slots": {"Сегодня": {"09:30", "10:30"}, "Завтра": set()},
        "time_slot_statuses": {
            ("Сегодня", "10:00"): "booked",
            ("Сегодня", "09:30"): "unavailable",
            ("Сегодня", "10:30"): "unavailable"
        }
    }

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("utils.time_utils.get_adjacent_time_slots", lambda slot: ["09:30", "10:30"])

    bot = Bot(token="123456:TEST_TOKEN_IS_OK")
    cb = DummyCallback(
        chat_id=40,
        data="group_status|G1|Сегодня|10:00|-1",
        bot=bot,
        user_id=7,
        user_status="administrator"
    )

    await admin_flow_module.admin_click_status(cb)

    # "10:00" удалён из booked_slots
    assert "10:00" not in admin_flow_module.groups_data["G1"]["booked_slots"]["Сегодня"]
    # Соседние слоты удалены из unavailable_slots
    assert admin_flow_module.groups_data["G1"]["unavailable_slots"]["Сегодня"] == set()
    # update_group_message вызван
    assert patch_update_group_message == ["G1"]
    # safe_answer содержал текст "Слот отменён."
    assert any("Слот отменён." in call_args[1][0] for call_args in patch_safe_answer)


@pytest.mark.asyncio
async def test_admin_click_status_set_status_and_payment(patch_safe_answer, patch_apply_special_user_reward):
    """
    Если code != "-1" и != "back" → обновляем time_slot_statuses, вызываем apply_special_user_reward,
    затем safe_answer с клавиатурой выбора оплаты.
    """
    admin_flow_module.groups_data["G1"] = {
        "chat_id": 50,
        "slot_bookers": {("Сегодня", "10:00"): 9},
        "booked_slots": {"Сегодня": ["10:00"], "Завтра": []},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "time_slot_statuses": {}
    }

    class FakeConn:
        async def execute(self, *args, **kwargs):
            return

        async def fetchrow(self, *args, **kwargs):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        async def acquire(self):
            return FakeConn()
        def __await__(self):
            yield

    import db
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(db, "db_pool", FakePool())

    bot = Bot(token="123456:TEST_TOKEN_IS_OK")
    some_code = list(status_mapping.keys())[0]
    cb = DummyCallback(
        chat_id=50,
        data=f"group_status|G1|Сегодня|10:00|{some_code}",
        bot=bot,
        user_id=9,
        user_status="creator"
    )

    await admin_flow_module.admin_click_status(cb)

    expected_emoji = status_mapping.get(some_code)
    assert admin_flow_module.groups_data["G1"]["time_slot_statuses"][("Сегодня", "10:00")] == expected_emoji
    assert patch_apply_special_user_reward == [some_code]

    # Один вызов safe_answer
    assert len(patch_safe_answer) == 1
    entity, args, kwargs = patch_safe_answer[0]
    assert kwargs.get("photo") == admin_flow_module.PHOTO_ID
    assert "Выберите способ оплаты:" in args[0]
    payment_kb = kwargs.get("reply_markup")
    assert hasattr(payment_kb, "inline_keyboard")
    assert len(payment_kb.inline_keyboard) == 3
    texts = [btn.callback_data for row in payment_kb.inline_keyboard for btn in row]
    assert any("cash" in t for t in texts)
    assert any("beznal" in t for t in texts)
    assert any("agent" in t for t in texts)


@pytest.mark.asyncio
async def test_admin_click_status_concurrent():
    """
    Одновременная обработка 10 запросов admin_click_status:
    все должны завершиться без ошибок.
    """
    admin_flow_module.groups_data["G1"] = {
        "chat_id": 999,
        "slot_bookers": {("Сегодня", "09:00"): 11},
        "booked_slots": {"Сегодня": ["09:00"], "Завтра": []},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "time_slot_statuses": {}
    }

    class FakeConn:
        async def execute(self, *args, **kwargs):
            return

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        async def acquire(self):
            return FakeConn()
        def __await__(self):
            yield

    import db
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(db, "db_pool", FakePool())
    monkeypatch.setattr("utils.time_utils.get_adjacent_time_slots", lambda slot: [])
    monkeypatch.setattr(admin_flow_module, "apply_special_user_reward", lambda code, b: asyncio.sleep(0))
    monkeypatch.setattr(admin_flow_module, "update_group_message", lambda b, g: asyncio.sleep(0))
    monkeypatch.setattr(admin_flow_module, "safe_answer", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr("utils.bot_utils.safe_answer", lambda *args, **kwargs: asyncio.sleep(0))

    bot = Bot(token="123456:TEST_TOKEN_IS_OK")

    async def simulate(user_id, code):
        cb = DummyCallback(
            chat_id=999,
            data=f"group_status|G1|Сегодня|09:00|{code}",
            bot=bot,
            user_id=user_id,
            user_status="administrator"
        )
        return await admin_flow_module.admin_click_status(cb)

    some_code = list(status_mapping.keys())[0]
    tasks = [simulate(200 + i, some_code) for i in range(10)]
    results = await asyncio.gather(*tasks)
    assert all(r is None for r in results)
