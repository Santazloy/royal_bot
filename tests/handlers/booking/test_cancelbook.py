import pytest
import asyncio

from aiogram import Bot
from aiogram.types import Chat, User, Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

import handlers.booking.cancelbook as cancelbook_module
import db
from constants.booking_const import groups_data


# ─────────────────────────────────────────────────────────────────────────────
#                        Вспомогательные заглушки / утилиты
# ─────────────────────────────────────────────────────────────────────────────

class DummyMessage(Message):
    """
    Pydantic-модель Message помечена frozen, поэтому from_user нужно задать прямо в __init__.
    """
    def __init__(self, chat_id: int, bot: Bot, from_user: User):
        chat = Chat(id=chat_id, type="supergroup")
        super().__init__(
            message_id=1234,
            date=0,
            chat=chat,
            from_user=from_user,
            text=""
        )
        object.__setattr__(self, "_bot", bot)

    @property
    def bot(self) -> Bot:
        return getattr(self, "_bot")


class DummyCallback(CallbackQuery):
    """
    Pydantic-модель CallbackQuery тоже frozen. Устанавливаем from_user в конструкторе
    и переопределяем .bot так, чтобы get_me() возвращал «бот» с ID ≠ from_user.id,
    а get_chat_member всегда возвращал ChatMember со статусом, как задано.
    """
    def __init__(self, chat_id: int, data: str, bot: Bot, user_id: int, user_status: str = "member"):
        user = User(id=user_id, is_bot=False, first_name="TestUser")
        msg = DummyMessage(chat_id=chat_id, bot=bot, from_user=user)
        super().__init__(
            id="0",  # id должен быть строкой
            from_user=user,
            chat_instance="dummy_instance",
            message=msg,
            data=data
        )
        object.__setattr__(self, "_user_status", user_status)

    @property
    def bot(self):
        class _BotStub:
            def __init__(inner_self, parent_cb):
                object.__setattr__(inner_self, "_parent", parent_cb)

            async def get_chat_member(inner_self, chat_id, user_id):
                from aiogram.types import ChatMember
                return ChatMember(
                    user=inner_self._parent.from_user,
                    status=inner_self._parent._user_status,
                    chat=Chat(id=chat_id, type="supergroup")
                )

            async def get_me(inner_self):
                # «Бот» с ID = −1 (не совпадёт с реальным user_id).
                class Me:
                    id = -1
                return Me()

            async def send_photo(inner_self, *args, **kwargs):
                # Если где-либо вызывается bot.send_photo, возвращаем «фейковый» ответ
                class FakeSent:
                    message_id = 777
                return FakeSent()

        return _BotStub(self)

    async def answer(self, text: str = None, show_alert: bool = False, **kwargs):
        # Простой заглушечный метод
        return


# ─────────────────────────────────────────────────────────────────────────────
#                    Dummy DBPool / Dummy DBConn (для async with)
# ─────────────────────────────────────────────────────────────────────────────

class DummyDBConn:
    def __init__(self, fetch_rows=None, fetchrow_data=None):
        self._fetch_rows = [] if fetch_rows is None else fetch_rows
        self._fetchrow_data = fetchrow_data

    async def fetch(self, query, *args, **kwargs):
        return self._fetch_rows

    async def fetchrow(self, query, *args, **kwargs):
        return self._fetchrow_data

    async def execute(self, *args, **kwargs):
        return

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyDBPool:
    """
    Реализуем acquire() как синхронный метод, возвращающий DummyDBConn.
    Тогда `async with db.db_pool.acquire() as conn:` будет работать без ошибок.
    """
    def __init__(self, fetch_rows=None, fetchrow_data=None):
        self._fetch_rows = [] if fetch_rows is None else fetch_rows
        self._fetchrow_data = fetchrow_data

    def acquire(self):
        return DummyDBConn(
            fetch_rows=self._fetch_rows,
            fetchrow_data=self._fetchrow_data
        )


@pytest.fixture(autouse=True)
def patch_db_pool(monkeypatch):
    """
    Во всех тестах подменяем db.db_pool на DummyDBPool. По умолчанию —
    пустая таблица (fetch_rows=[]), fetchrow_data=None.
    """
    import db as _db
    pool = DummyDBPool(fetch_rows=[], fetchrow_data=None)
    monkeypatch.setattr(_db, "db_pool", pool)
    yield pool
    monkeypatch.setattr(_db, "db_pool", None)


@pytest.fixture(autouse=True)
def clear_groups_data():
    """
    Перед каждым тестом сохраняем текущее groups_data, очищаем его
    и после теста возвращаем исходное содержимое.
    """
    original = groups_data.copy() if hasattr(groups_data, "copy") else {}
    groups_data.clear()
    yield
    groups_data.clear()
    groups_data.update(original)


@pytest.fixture(autouse=True)
def patch_safe_answer(monkeypatch):
    """
    Подменяем safe_answer _внутри_ cancelbook_module и в utils.bot_utils,
    чтобы не делать реальных HTTP‐запросов и отслеживать, с какими параметрами он вызван.
    """
    calls = []

    async def fake_safe_answer(entity, *args, **kwargs):
        calls.append((entity, args, kwargs))
        class Sent:
            message_id = 999
        return Sent()

    monkeypatch.setattr(cancelbook_module, "safe_answer", fake_safe_answer)
    monkeypatch.setattr("utils.bot_utils.safe_answer", fake_safe_answer, raising=False)
    return calls


@pytest.fixture(autouse=True)
def patch_update_group_message(monkeypatch):
    """
    Подменяем update_group_message внутри cancelbook_module,
    чтобы просто писать в список вызовов, но не отправлять реальный message.
    """
    calls = []

    async def fake_update_group_message(bot, group_key):
        calls.append(group_key)
        return

    monkeypatch.setattr(cancelbook_module, "update_group_message", fake_update_group_message, raising=False)
    return calls


@pytest.fixture(autouse=True)
def patch_adjacent_slots(monkeypatch):
    """
    Подменяем get_adjacent_time_slots внутри cancelbook_module,
    чтобы не иметь зависимости от реального расписания.
    """
    monkeypatch.setattr(cancelbook_module, "get_adjacent_time_slots", lambda slot: [], raising=False)
    return


# ─────────────────────────────────────────────────────────────────────────────
#                                 Тесты
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cmd_off_no_db(patch_safe_answer, patch_db_pool):
    """
    Если db.db_pool = None, cmd_off сразу вызывает safe_answer("База данных не инициализирована.").
    """
    import db as _db
    _db.db_pool = None

    bot = Bot(token="123:TEST")
    from_user = User(id=42, is_bot=False, first_name="TestUser")
    msg = DummyMessage(chat_id=123, bot=bot, from_user=from_user)

    await cancelbook_module.cmd_off(msg)

    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]

    # В args[0] лежит текст, который get_message вернул для ключа "db_not_initialized"
    assert "База данных не инициализирована" in args[0]
    assert kwargs.get("photo") == cancelbook_module.PHOTO_ID


@pytest.mark.asyncio
async def test_cmd_off_user_no_bookings(patch_safe_answer, patch_db_pool):
    """
    Если у пользователя нет бронирований (fetch вернул пустой список),
    cmd_off должен вызвать safe_answer("Нет активных бронирований.").
    """
    patch_db_pool._fetch_rows = []  # Пустой список Booking-записей

    bot = Bot(token="123:TEST")
    from_user = User(id=7, is_bot=False, first_name="User7")
    msg = DummyMessage(chat_id=555, bot=bot, from_user=from_user)

    await cancelbook_module.cmd_off(msg)

    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]
    assert "Нет активных бронирований" in args[0]
    assert kwargs.get("photo") == cancelbook_module.PHOTO_ID


@pytest.mark.asyncio
async def test_cmd_off_user_with_bookings(patch_safe_answer, patch_db_pool):
    """
    Если у пользователя есть две записи, cmd_off строит клавиатуру с двумя кнопками:
      off_cancel_user_100 и off_cancel_user_101, и текст «Выберите бронирование для отмены».
    """
    # Делаем так, чтобы fetch() вернул два “row”
    row1 = {"id": 100, "group_key": "G1", "day": "Today", "time_slot": "10:00"}
    row2 = {"id": 101, "group_key": "G2", "day": "Tomorrow", "time_slot": "11:30"}
    patch_db_pool._fetch_rows = [row1, row2]

    bot = Bot(token="123:TEST")
    from_user = User(id=7, is_bot=False, first_name="User7")
    msg = DummyMessage(chat_id=555, bot=bot, from_user=from_user)

    await cancelbook_module.cmd_off(msg)

    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]

    # Проверяем текст приглашения:
    assert "Выберите бронирование для отмены" in args[0]
    assert kwargs.get("photo") == cancelbook_module.PHOTO_ID

    # Проверяем сам InlineKeyboardMarkup:
    kb: InlineKeyboardMarkup = kwargs.get("reply_markup")
    assert hasattr(kb, "inline_keyboard")

    rows = kb.inline_keyboard
    assert len(rows) == 2

    # Первая кнопка должна иметь callback_data "off_cancel_user_100"
    assert rows[0][0].callback_data == "off_cancel_user_100"
    assert "❌ Today 10:00 (G1)" in rows[0][0].text

    # Вторая кнопка — "off_cancel_user_101"
    assert rows[1][0].callback_data == "off_cancel_user_101"
    assert "❌ Tomorrow 11:30 (G2)" in rows[1][0].text


@pytest.mark.asyncio
async def test_off_cancel_user_not_found(patch_safe_answer, patch_db_pool, patch_update_group_message):
    """
    Пользователь нажал «off_cancel_user_…», но fetchrow вернул None:
    off_cancel_user должен вызвать safe_answer("Нет такой брони."), show_alert=True;
    update_group_message при этом не вызывается, а groups_data не меняется.
    """
    patch_db_pool._fetchrow_data = None  # эмулируем, что в БД нет записи с таким ID

    # Чтобы удостовериться, что groups_data не испортилось, добавим фиктивную группу:
    groups_data["G1"] = {
        "chat_id": 40,
        "slot_bookers": {("Today", "10:00"): 7},
        "booked_slots": {"Today": ["10:00"], "Tomorrow": []},
        "unavailable_slots": {"Today": set(), "Tomorrow": set()},
        "time_slot_statuses": {}
    }

    bot = Bot(token="123:TEST")
    # Пользователь пытается отменить несуществующую бронь 999
    cb = DummyCallback(chat_id=40, data="off_cancel_user_999", bot=bot, user_id=7, user_status="member")

    await cancelbook_module.off_cancel_user(cb, state=None)

    # safe_answer("Нет такой брони.", show_alert=True) — должен быть ровно 1 вызов
    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]
    assert "Нет такой брони" in args[0]
    assert kwargs.get("show_alert") is True

    # update_group_message НЕ должен вызываться:
    assert patch_update_group_message == []

    # А groups_data осталась прежней (слот "10:00" всё ещё есть)
    assert "10:00" in groups_data["G1"]["booked_slots"]["Today"]


@pytest.mark.asyncio
async def test_off_cancel_user_success(patch_safe_answer, patch_db_pool, patch_update_group_message):
    """
    Если fetchrow вернул реальный словарь с group_key/ day / time_slot,
    off_cancel_user должен:
      – удалять запись из in-memory groups_data,
      – вызывать update_group_message(bot, гk),
      – вызывать safe_answer("Бронирование отменено."), show_alert=True.
    """
    patch_db_pool._fetchrow_data = {"group_key": "G1", "day": "Today", "time_slot": "10:00"}

    groups_data["G1"] = {
        "chat_id": 40,
        "slot_bookers": {("Today", "10:00"): 7},
        "booked_slots": {"Today": ["10:00"], "Tomorrow": []},
        "unavailable_slots": {"Today": set(), "Tomorrow": set()},
        "time_slot_statuses": {("Today", "10:00"): "booked"}
    }

    bot = Bot(token="123:TEST")
    cb = DummyCallback(chat_id=40, data="off_cancel_user_555", bot=bot, user_id=7, user_status="member")

    await cancelbook_module.off_cancel_user(cb, state=None)

    # «10:00» должен исчезнуть из booked_slots
    assert "10:00" not in groups_data["G1"]["booked_slots"]["Today"]
    # slot_bookers и time_slot_statuses тоже не должны содержать этот слот
    assert ("Today", "10:00") not in groups_data["G1"]["slot_bookers"]
    assert ("Today", "10:00") not in groups_data["G1"]["time_slot_statuses"]

    # update_group_message должен был вызваться ровно один раз с «G1»:
    assert patch_update_group_message == ["G1"]

    # safe_answer("Бронирование отменено."), show_alert=True
    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]
    assert "Бронирование отменено" in args[0]
    assert kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_cmd_off_admin_no_db(patch_safe_answer, patch_db_pool):
    """
    Если db.db_pool = None, cmd_off_admin сразу вызывает safe_answer("База данных не инициализирована.").
    """
    import db as _db
    _db.db_pool = None

    bot = Bot(token="123:TEST")
    from_user = User(id=99, is_bot=False, first_name="Admin99")
    msg = DummyMessage(chat_id=1, bot=bot, from_user=from_user)

    await cancelbook_module.cmd_off_admin(msg)

    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]
    assert "База данных не инициализирована" in args[0]


@pytest.mark.asyncio
async def test_cmd_off_admin_no_bookings(patch_safe_answer, patch_db_pool):
    """
    Если в таблице нет броней, cmd_off_admin вызывает safe_answer("Нет активных бронирований.").
    """
    patch_db_pool._fetch_rows = []

    bot = Bot(token="123:TEST")
    from_user = User(id=99, is_bot=False, first_name="Admin99")
    msg = DummyMessage(chat_id=1, bot=bot, from_user=from_user)

    await cancelbook_module.cmd_off_admin(msg)

    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]
    assert "Нет активных бронирований" in args[0]


@pytest.mark.asyncio
async def test_cmd_off_admin_with_bookings(patch_safe_answer, patch_db_pool):
    """
    Если fetch вернул несколько строк, cmd_off_admin строит клавиатуру с кнопками
    off_cancel_admin_{id} и текстом «Выберите бронирование для отмены».
    """
    row1 = {"id": 200, "group_key": "G1", "day": "Today", "time_slot": "08:00"}
    row2 = {"id": 201, "group_key": "G2", "day": "Tomorrow", "time_slot": "09:30"}
    patch_db_pool._fetch_rows = [row1, row2]

    bot = Bot(token="123:TEST")
    from_user = User(id=99, is_bot=False, first_name="Admin99")
    msg = DummyMessage(chat_id=1, bot=bot, from_user=from_user)

    await cancelbook_module.cmd_off_admin(msg)

    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]

    # Текст должен содержать «Выберите бронирование для отмены»
    assert "Выберите бронирование для отмены" in args[0]

    kb: InlineKeyboardMarkup = kwargs.get("reply_markup")
    rows = kb.inline_keyboard
    assert len(rows) == 2
    assert rows[0][0].callback_data == "off_cancel_admin_200"
    assert "❌ Today 08:00 (G1)" in rows[0][0].text
    assert rows[1][0].callback_data == "off_cancel_admin_201"
    assert "❌ Tomorrow 09:30 (G2)" in rows[1][0].text


@pytest.mark.asyncio
async def test_off_cancel_admin_not_found(patch_safe_answer, patch_db_pool, patch_update_group_message):
    """
    Админ нажал off_cancel_admin_… но fetchrow вернул None:
    off_cancel_admin должен вызвать safe_answer("Нет такой брони."), show_alert=True,
    а update_group_message не должен вызываться.
    """
    patch_db_pool._fetchrow_data = None

    bot = Bot(token="123:TEST")
    cb = DummyCallback(chat_id=1, data="off_cancel_admin_999", bot=bot, user_id=99, user_status="administrator")

    await cancelbook_module.off_cancel_admin(cb, state=None)

    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]
    assert "Нет такой брони" in args[0]
    assert kwargs.get("show_alert") is True

    # update_group_message не должен вызываться
    assert patch_update_group_message == []


@pytest.mark.asyncio
async def test_off_cancel_admin_success(patch_safe_answer, patch_db_pool, patch_update_group_message):
    """
    Если fetchrow вернул {"group_key":"G1","day":"Today","time_slot":"08:00"},
    off_cancel_admin должен:
      – удалить запись (эмулировано),
      – вызвать update_group_message("G1"),
      – вызвать safe_answer("Бронирование отменено администратором."), show_alert=True.
    """
    patch_db_pool._fetchrow_data = {"group_key": "G1", "day": "Today", "time_slot": "08:00"}

    bot = Bot(token="123:TEST")
    cb = DummyCallback(chat_id=1, data="off_cancel_admin_300", bot=bot, user_id=99, user_status="administrator")

    await cancelbook_module.off_cancel_admin(cb, state=None)

    # update_group_message должен быть вызван c "G1"
    assert patch_update_group_message == ["G1"]

    # safe_answer("Бронирование отменено администратором."), show_alert=True
    assert len(patch_safe_answer) == 1
    _entity, args, kwargs = patch_safe_answer[0]
    assert "Бронирование отменено администратором" in args[0]
    assert kwargs.get("show_alert") is True
