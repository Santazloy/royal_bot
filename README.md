# Часть 1. Developer Documentation (`royal_bot`)

## 1. Введение

**`royal_bot`** — это асинхронный Telegram-бот на базе **Aiogram** (Python), предназначенный для:
- Организации бронирования временных слотов в нескольких Telegram-группах.
- Автоматизированного ведения финансовых отчётов: зарплата, наличные, баланс пользователей.
- Управления пользователями через систему эмодзи (назначение, ротация).
- Поддержки многоязычности (русский, английский, китайский).
- Административного меню с возможностью:
  - Просмотра и корректировки зарплаты для групп.
  - Назначения эмодзи пользователям.
  - Обработки статусов брони (✅, ❌ и др.).
  - Управления оплатой (наличные, безнал, агент).
  - Ежедневного сброса «Завтра» → «Сегодня» с генерацией отчётов.
- Хранения данных в PostgreSQL и кэширования текущих состояний групп в памяти.

Репозиторий структурирован по модулям:
- `handlers/` — обработчики команд и колбэков (FSM-сценарии, админ-меню, пользовательский интерфейс).
- `constants/` — константы проекта: ключи групп, параметры зарплаты, статус-эмодзи.
- `utils/` — вспомогательные утилиты (работа с базой, форматирование текста, генерация слотов).
- `db_access/` — абстракция доступа к данным (репозиторий бронирований).
- `main.py`, `config.py`, `db.py` — точка входа, конфигурация, инициализация БД.

### 1.1. База данных (PostgreSQL)

#### 1.1.1. Таблицы

- **users**
  - `user_id` (PK, bigint)
  - `username` (text)
  - `balance` (numeric)
  - `profit` (numeric)
  - `monthly_profit` (numeric)

- **user_emojis**
  - `user_id` (PK, bigint, FK → users)
  - `emojis` (text) — запятая-разделённый список эмодзи

- **user_settings**
  - `user_id` (PK, bigint, FK → users)
  - `language` (char(2))

- **bookings**
  - `group_key` (text)
  - `day` (text, "Сегодня" / "Завтра")
  - `time_slot` (text, формат `HH:MM`)
  - `user_id` (bigint, FK → users)
  - `status_code` (text)
  - `status` (text, эмодзи статуса)
  - `amount` (integer)
  - `payment_method` (text, "cash", "beznal", "agent")
  - `emoji` (text)
  - **CONSTRAINT**: уникальность `(group_key, day, time_slot)`

- **group_time_slot_statuses**
  - `group_key` (text)
  - `day` (text)
  - `time_slot` (text)
  - `status` (text)
  - `user_id` (bigint)
  - **CONSTRAINT**: уникальность `(group_key, day, time_slot)`

- **group_financial_data**
  - `group_key` (PK, text)
  - `salary_option` (integer, 1–4)
  - `salary` (numeric)
  - `cash` (numeric)
  - `message_id` (integer) — ID последнего отправленного группового сообщения

#### 1.1.2. Логика взаимодействия

1. **Инициализация**
   - При старте `main.py` вызывает:
     - `load_salary_data_from_db()` (в `handlers/salary.py`) — заполняет `groups_data` данными из `group_financial_data`.
     - `load_slots_from_db()` (в `handlers/booking/loader.py`) — заполняет in-memory `groups_data` данными из таблиц `bookings` и `group_time_slot_statuses`.
2. **Запись бронирования**
   - `async_book_slot()` (в `handlers/booking/data_manager.py`):
     1. Получает следующее эмодзи через `get_next_emoji()`.
     2. Записывает запись в таблицу `bookings` со статусом "booked" и эмодзи.
     3. Обновляет in-memory `groups_data`: `booked_slots`, `slot_bookers`, `time_slot_statuses`, `slot_emojis`, `unavailable_slots`.
3. **Обновление статуса слота**
   - Администратор выбирает слот в групповом сообщении → callback "group_time|..." (в `handlers/booking/admin_flow.py`).
   - После выбора статуса:
     - Обновляется `bookings.status_code/status`.
     - Вставляется или обновляется запись в `group_time_slot_statuses`.
     - Вызывается `apply_special_user_reward()` при необходимости.
     - Формируется клавиатура оплаты.
4. **Оплата и расчёт**
   - В `handlers/booking/payment_flow.py`:
     - Админ выбирает метод оплаты (cash, beznal, agent).
     - Если cash/beznal → FSM запрашивает сумму, затем:
       - Вычисляются выплата (base) и комиссия (deduct) по статусу.
       - `groups_data[group]["salary"] += base`; при cash → `groups_data[group]["cash"] += amount`.
       - Обновляется `group_financial_data`.
       - Обновляется `bookings.payment_method` и `bookings.amount`.
       - Вызывается `update_user_financial_info()` для пользователя (списание/начисление).
       - При настроенной `distribution_variant` начисление ещё одному пользователю.
       - `update_group_message()` и `send_financial_report()`.
     - Если agent → аналогичный расчёт, но без запроса суммы, напрямую.
5. **Ежедневный сброс ("Завтра" → "Сегодня")**
   - `handlers/next.py → do_next_core(bot)`:
     1. Сбор отчёта за "Сегодня" (количество бронирований, суммы по методам, разбивка по пользователям).
     2. Отправка отчёта в чат `FINANCIAL_REPORT_GROUP_ID`.
     3. Удаление всех записей "Сегодня" из `bookings` и `group_time_slot_statuses`.
     4. Очистка in-memory для "Сегодня".
     5. Перенос записей "Завтра" → "Сегодня" в БД и in-memory.
     6. Обновление `groups_data` структур для новых значений.
     7. Вызов `update_group_message()` для каждой группы.
   - Планировщик в `register_daily_scheduler()` проверяет время в Asia/Shanghai: ровно 03:00 запуск `do_next_core()`.
6. **Управление эмодзи**
   - `handlers/startemoji.py`:
     - `/start`:
       - Если у пользователя нет эмодзи → уведомление `ADMIN_IDS` для назначения.
       - Если эмодзи есть → приветственное сообщение.
     - `/emoji` (или админ-меню) → список пользователей из `users` → кнопки `assign_emoji_<user_id>`.
     - Callback `assign_emoji_<target_id>` → клавиатура `CUSTOM_EMOJIS` и `TRIPLE_EMOJIS`.
     - Выбор (одного/нескольких) эмодзи → сохранение в `user_emojis` и уведомление пользователя.
     - `get_next_emoji(user_id)` циклически выдаёт текущее эмодзи или инициализирует "👤".
7. **Многоязычность**
   - `handlers/language.py`:
     - `TRANSLATIONS[key][lang]`: ключи и переводы.
     - Таблица `user_settings(user_id, language)`.
     - `/lang` → клавиатура выбора языка (InlineKeyboardButton(text, callback_data="setlang_<code>")).
     - Callback `setlang_<code>` → сохранение и уведомление.
8. **Админ-меню (`handlers/menu_ad.py`)**
   - `/ad` → меню с кнопками:
     ```
     Леонард | Зарплата
     Эмодзи | Деньги
     Отмена брони | Очистка
     Балансы | Правила
     Конвертация | Сброс дня
     Назад
     ```
   - Каждая кнопка вызывает соответствующий callback: `leonard_menu_callback`, `salary_command`, `cmd_emoji`, `money_command`, `cmd_off_admin`, `clean_via_button`, `show_users_via_callback`, `callback_reset_day`.
9. **Пользовательское меню (`handlers/menu_user.py`)**
   - `/menu` → фото + кнопки:
     - Бронирование (`menu_stub|booking`)
     - Расписание (`view_all_bookings`)
     - Баланс (`menu_stub|balance`)
     - Отмена брони (`menu_stub|cancel_booking`)
   - Выбор `menu_stub|booking` запускает FSM из `handlers/booking/user_flow.py`.
   - `menu_stub|cancel_booking` вызывает `cmd_off()` из `handlers/booking/cancelbook.py`.
10. **FSM-состояния**
    - `handlers/states.py`:
      ```
      class BookUserStates(StatesGroup):
          waiting_for_group = State()
          waiting_for_day = State()
          waiting_for_time = State()

      class BookPaymentStates(StatesGroup):
          waiting_for_amount = State()

      class SalaryStates(StatesGroup):
          waiting_for_group_choice = State()
          waiting_for_option_choice = State()

      class EmojiStates(StatesGroup):
          waiting_for_assign = State()

      class AdminStates(StatesGroup):
          menu = State()
      ```
11. **Утилиты (`utils/`)**
    - **`bot_utils.py`**
      - `safe_answer(entity, ...)` — унифицированная отправка ответа, удаление предыдущего сообщения, обработка ошибок.
      - `last_bot_message: Dict[int, int]` — позволяет удалять предыдущие сообщения перед отправкой новых (используется в `send_tracked()`).
    - **`text_utils.py`**
      - `format_html_pre(text)` — возвращает строку в теге `<pre>…</pre>`.
    - **`time_utils.py`**
      - `generate_daily_time_slots()` — генерация списка слотов `["00:00", "00:30", …, "23:30"]`.
      - `get_adjacent_time_slots(slot)` — список соседних слотов (±30 мин).
12. **Константы (`constants/`)**
    - **`booking_const.py`**
      - `groups_data: Dict[str, Dict[str, Any]]` — in-memory структура с ключами групп и метаданными:
        ```
        groups_data = {
            "Royal_1": {
                "chat_id": -1002503654146,
                "salary_option": 1,
                "salary": 0,
                "cash": 0,
                "time_slot_statuses": {},
                "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
                "booked_slots": {"Сегодня": [], "Завтра": []},
                "slot_bookers": {},
                "slot_emojis": {},
                "target_id": None,
                "distribution_variant": None,
                "message_id": None
            },
            # Остальные группы аналогично
        }
        ```
      - `status_mapping: Dict[str, str]` — отображение кода статуса в эмодзи (например, "0" → "❌❌❌", "1" → "✅", …).
      - `distribution_variants: Dict[str, Dict[str, int]]` — параметры дополнительного распределения оплаты.
      - `BOOKING_REPORT_GROUP_ID`, `FINANCIAL_REPORT_GROUP_ID` — ID чатов для отчётов.
    - **`salary.py`**
      - `salary_options: Dict[int, Dict[str, int]]` — базовые выплаты по статусам для опций 1–4:
        ```
        salary_options = {
            1: {'✅':700,  '✅2':900,  '✅✅':1400, '✅✅✅':2100},
            2: {'✅':800,  '✅2':1000, '✅✅':1600, '✅✅✅':2400},
            3: {'✅':900,  '✅2':1100, '✅✅':1800, '✅✅✅':2700},
            4: {'✅':1000, '✅2':1200, '✅✅':2000, '✅✅✅':3000},
        }
        ```

---

## 2. Описание ключевых компонентов

### 2.1. `main.py`
- **Инициализация**:
  1. Загружает переменные окружения: `BOT_TOKEN`, `DATABASE_URL`, `ADMIN_IDS`, `BOOKING_REPORT_GROUP_ID`, `FINANCIAL_REPORT_GROUP_ID`.
  2. Создаёт пул соединений `db.db_pool` для PostgreSQL (модуль `db.py`).
  3. Вызывает:
     - `handlers/salary.load_salary_data_from_db()` — загружает данные `group_financial_data` в `groups_data`.
     - `handlers/booking/loader.load_slots_from_db()` — загружает записи `bookings` и `group_time_slot_statuses` в `groups_data`.
  4. Инициализирует бота и диспетчер (`Dispatcher`).
  5. Регистрирует все маршрутизаторы (`handlers/*`) с помощью `dp.include_router(...)`.
  6. Устанавливает команды бота (`bot.set_my_commands(...)`).
  7. (Опционально) Если используется планировщик, вызывает `handlers/next.register_daily_scheduler(dp, bot)`.
  8. Запускает polling (`dp.start_polling()`).

### 2.2. `config.py`
- Хранит базовые настройки:
  - `BOT_TOKEN: str` — токен Telegram-бота.
  - `ADMIN_IDS: List[int]` — список ID администраторов.
  - `BOOKING_REPORT_GROUP_ID: int`
  - `FINANCIAL_REPORT_GROUP_ID: int`
  - Пути к изображениям (например, `STARTEMOJI_PHOTO`, `MENU_PHOTO_ID`).
- Функция `is_user_admin(user_id: int) -> bool` проверяет, есть ли `user_id` в `ADMIN_IDS`.

### 2.3. `db.py`
- Создаёт и экспортирует глобальный пул соединений:
  ```python
  import os
  import asyncpg

  db_pool = None

  async def init_db_pool():
      global db_pool
      db_pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))
  ```
- Вызывается из `main.py` перед регистрацией хендлеров.

### 2.4. `constants/booking_const.py`
```python
from typing import Dict, Any
import os

# In-memory структуры для групп:
groups_data: Dict[str, Dict[str, Any]] = {
    "Royal_1": {
        "chat_id": -1002503654146,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {"Сегодня": set(), "Завтра": set()},
        "booked_slots": {"Сегодня": [], "Завтра": []},
        "slot_bookers": {},
        "slot_emojis": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None,
    },
    # … аналоги для других групп …
}

# Отображение status_code → emoji
status_mapping: Dict[str, str] = {
    "0": "❌❌❌",
    "1": "✅",
    "2": "✅2",
    "3": "✅✅",
    "4": "✅✅✅",
}

# Варианты распределения доп. оплаты
distribution_variants: Dict[str, Dict[str, int]] = {
    "variant_400": {"1": 400, "2": 600, "3": 800, "4": 1000},
}

BOOKING_REPORT_GROUP_ID: int = int(os.getenv("BOOKING_REPORT_GROUP_ID", "-100"))
FINANCIAL_REPORT_GROUP_ID: int = int(os.getenv("FINANCIAL_REPORT_GROUP_ID", "-100"))
```

### 2.5. `constants/salary.py`
```python
salary_options: Dict[int, Dict[str, int]] = {
    1: {'✅': 700,  '✅2': 900,  '✅✅': 1400, '✅✅✅': 2100},
    2: {'✅': 800,  '✅2': 1000, '✅✅': 1600, '✅✅✅': 2400},
    3: {'✅': 900,  '✅2': 1100, '✅✅': 1800, '✅✅✅': 2700},
    4: {'✅': 1000, '✅2': 1200, '✅✅': 2000, '✅✅✅': 3000},
}
```

### 2.6. `handlers/startemoji.py`
... *(уже описано в предыдущей секции; аналогично)*

### 2.7. `handlers/menu_ad.py`
... *(уже описано в предыдущей секции; аналогично)*

### 2.8. `handlers/menu_user.py`
... *(уже описано в предыдущей секции; аналогично)*

### 2.9. `handlers/language.py`
... *(уже описано в предыдущей секции; аналогично)*

---

# Часть 2. User Guide (Инструкция для пользователей)

## 1. Начало работы

1. Добавьте бота в Telegram по его @username (например, `@Royalaiagent_bot`).
2. Отправьте команду:
   ```
   /start
   ```
   - Если у вас ещё нет эмодзи, бот уведомит администраторов и сообщит:
     ```
     Ожидайте — ваш аккаунт отправлен на рассмотрение администратору.
     ```
   - После назначения эмодзи вы получите:
     ```
     Добро пожаловать! Эмодзи уже назначен.
     ```
3. При необходимости выберите язык:
   ```
   /lang
   ```
   Нажмите на нужный:
   - English
   - Русский
   - 中文

## 2. Основные команды

### 2.1. `/menu`

Выводит главное меню с кнопками:
- **🅱️ Бронирование** — начать процесс бронирования.
- **📆 Расписание** — просмотреть все активные бронирования.
- **🧧 Баланс** — показать ваш текущий баланс (если включено).
- **❌ Отмена брони** — отменить текущее бронирование.

### 2.2. Процесс бронирования

1. Нажмите **🅱️ Бронирование**.
2. Выберите группу (например, `Royal_1`).
3. Выберите день:
   - Сегодня
   - Завтра
4. Выберите свободный временной слот (формат `HH:MM`). Доступны только незабронированные и незаблокированные (смежными) слоты.
5. После выбора вы увидите:
   ```
   🎉 {Ваше_имя}, вы забронировали слот на {HH:MM} ({день}) в группе Royal_X
   ```
6. В личных сообщениях придёт отчёт:
   ```
   📅 Новый Booking
   👤 Пользователь: {ваше_эмодзи} {ваше_имя}
   🌹 Группа: Royal_X
   ⏰ Время: {HH:MM} ({день})
   ```

### 2.3. Просмотр расписания

- Нажмите **📆 Расписание**.
- Бот отредактирует сообщение и покажет таблицу:
  ```
  📅 Все бронирования на Сегодня
  ╔══════════╦════════════════════╗
  ║ Группа   ║ Время бронирования ║
  ╠══════════╬════════════════════╣
  ║ Royal_1  ║ 19:00   🏀         ║
  ║ Royal_2  ║ 20:30   🏈         ║
  ╚══════════╩════════════════════╝
  ```

### 2.4. Отмена бронирования

1. Нажмите **❌ Отмена брони**.
2. Бот покажет ваши активные бронирования:
   ```
   [Royal_1 | 19:00 | Сегодня]
   [Royal_3 | 20:30 | Завтра]
   ```
3. Нажмите нужный слот.
4. Получите подтверждение:
   ```
   Бронирование отменено.
   ```

### 2.5. Просмотр баланса

- Нажмите **🧧 Баланс**.
- Бот ответит:
  ```
  Ваш баланс: {balance}¥
  ```
- При изменении баланса бот отправит личное сообщение:
  ```
  Ваш баланс изменён: +{amount}. Текущий баланс: {new_balance}¥
  ```

### 2.6. Выбор языка

- Нажмите:
  ```
  /lang
  ```
- Выберите:
  - English
  - Русский
  - 中文
- Бот подтвердит:
  ```
  Язык установлен на {lang_name}.
  ```

---

# Часть 3. Admin Guide (Инструкция для администраторов)

## 1. Общая информация

- **Проектный админ** — Telegram-ID из `config.ADMIN_IDS`. Полный доступ ко всему функционалу.
- **Админ группы** — статус "administrator" или "creator" в конкретной группе. Может управлять бронированиями и оплачивать слоты.

## 2. Назначение эмодзи пользователям

1. Пользователь отправляет `/start`, не имея эмодзи.
2. Бот отправляет всем `ADMIN_IDS` уведомление:
   ```
   Пользователь @username (ID: {user_id}) ожидает назначения эмодзи.
   [Кнопка «Назначить эмодзи»]
   ```
3. Админ нажимает «Назначить эмодзи».
4. Бот показывает клавиатуру с эмодзи (`CUSTOM_EMOJIS`) и кнопкой `⚽️🪩🏀`.
5. Админ выбирает один или несколько эмодзи.
6. Бот сохраняет их в `user_emojis` и отправляет пользователю:
   ```
   Вам назначен эмодзи: {emoji}
   Теперь доступны все команды!
   ```
7. Админ получает подтверждение:
   ```
   Пользователю {target_id} назначен эмодзи: {emoji}
   ```

## 3. Админ-меню `/ad`

1. Введите:
   ```
   /ad
   ```
2. Бот покажет фото с кнопками:
   ```
   🐆 Леонард   | 💰 Зарплата
   😊 Эмодзи    | 💵 Деньги
   ❌ Отмена брони | 🧹 Очистка
   📊 Балансы   | 📜 Правила
   🔄 Конвертация | 🔁 Сброс дня
   🔙 « Назад
   ```
3. Каждая кнопка запускает соответствующий модуль:
   - **Леонард** → `handlers/leonard.leonard_menu_callback()`
   - **Зарплата** → `handlers/salary.salary_command()`
   - **Эмодзи** → `handlers/startemoji.cmd_emoji()`
   - **Деньги** → `handlers/money.money_command()`
   - **Отмена брони** → `handlers/booking/cancelbook.cmd_off_admin()`
   - **Очистка** → `handlers/clean.clean_via_button()`
   - **Балансы** → `handlers/users.show_users_via_callback()`
   - **Правила**, **Конвертация** → заглушка ("Не реализовано")
   - **Сброс дня** → `handlers/next.callback_reset_day()`
   - **Назад** → выход из меню (очистка FSM)

### 3.1. Управление зарплатой

1. Нажмите **💰 Зарплата**.
2. Выберите группу (кнопка `salary_group_<group_key>`).
3. Выберите опцию (1–4) (`salary_opt_<opt>`).
4. Бот сохранит `salary_option` в `groups_data` и БД.
5. Подтверждение:
   ```
   Опция зарплаты для {group_key} установлена: {opt}.
   ```

### 3.2. Управление эмодзи

- Нажмите **😊 Эмодзи**.
- Бот покажет всех пользователей (`SELECT user_id, username FROM users`).
- Нажмите на пользователя → `assign_emoji_<user_id>` → выбирайте эмодзи.
- Подробности: раздел "Назначение эмодзи" (см. выше).

### 3.3. Управление финансами (Деньги)

1. Нажмите **💵 Деньги**.
2. Бот спросит: "Что изменить?" (Salary / Cash).
3. Выберите группу.
4. Выберите операцию (+ / −).
5. Введите сумму.
6. Бот обновит `group_financial_data` и `groups_data`.
7. Подтверждение:
   ```
   [Salary/Cash] для группы {group_key} изменено на {amount}¥.
   ```

### 3.4. Отмена брони

- Нажмите **❌ Отмена брони**.
- Бот покажет список всех слотов в статусе "booked".
- Выберите слот → бот удалит запись из `bookings` и `group_time_slot_statuses`, обновит in-memory, вызовет `update_group_message()`.
- Сообщение:
   ```
   Слот отменён.
   ```

### 3.5. Очистка данных

1. Нажмите **🧹 Очистка**.
2. FSM:
   - Шаг "Что стереть?" (Time / Salary / Cash / All).
   - Шаг "Выберите группу или 'Стереть все {section}'".
   - Подтверждение "Да, стереть".
3. Бот удалит:
   - Для Time — все брони (таблицы `bookings` и `group_time_slot_statuses`).
   - Для Salary — сбросит `salary = 0` (in-memory и БД).
   - Для Cash — аналогично.
   - Для All — всё перечисленное.
4. Подтвердит:
   ```
   Данные "{section}" стерты для {группа/всех групп}.
   ```

### 3.6. Просмотр балансов

- Нажмите **📊 Балансы**.
- Бот покажет:
   ```
   1. 😃 User1: 1200¥
   2. 🤖 User2: 800¥
   ...
   ```

### 3.7. Правила / Конвертация

- Пока не реализовано:
   ```
   Не реализовано
   ```

### 3.8. Сброс дня

- **Кнопка** **🔁 Сброс дня** (или `/next`):
  - Бот выполняет `do_next_core()`:
    1. Формирование отчёта за "Сегодня".
    2. Отправка в `FINANCIAL_REPORT_GROUP_ID`.
    3. Удаление записей "Сегодня" из `bookings` и `group_time_slot_statuses`.
    4. Перенос "Завтра" → "Сегодня" (БД и in-memory).
    5. Обновление `update_group_message()` во всех группах.
  - Уведомление:
    ```
    ✅ Отчет сформирован, бронирования перенесены.
    ```

## 4. Развёртывание

1. **Клонировать репозиторий**:
   ```
   git clone <repo_url>
   cd royal_bot
   ```
2. **Настроить виртуальное окружение**:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Установить зависимости**:
   ```
   pip install -r requirements.txt
   ```
4. **Создать .env** (или экспортировать переменные):
   ```
   BOT_TOKEN=your_token
   DATABASE_URL=postgresql://user:pass@host:port/dbname
   ADMIN_IDS=7894353415,7935161063,1768520583,7900291243
   BOOKING_REPORT_GROUP_ID=-1001234567890
   FINANCIAL_REPORT_GROUP_ID=-1009876543210
   ```
5. **Инициализировать БД** (SQL-схемы):
   ```sql
   CREATE TABLE users (
     user_id bigint PRIMARY KEY,
     username text,
     balance numeric DEFAULT 0,
     profit numeric DEFAULT 0,
     monthly_profit numeric DEFAULT 0
   );
   CREATE TABLE user_emojis (
     user_id bigint PRIMARY KEY REFERENCES users(user_id),
     emojis text
   );
   CREATE TABLE user_settings (
     user_id bigint PRIMARY KEY REFERENCES users(user_id),
     language char(2)
   );
   CREATE TABLE bookings (
     group_key text,
     day text,
     time_slot text,
     user_id bigint REFERENCES users(user_id),
     status_code text,
     status text,
     amount integer,
     payment_method text,
     emoji text,
     PRIMARY KEY (group_key, day, time_slot)
   );
   CREATE TABLE group_time_slot_statuses (
     group_key text,
     day text,
     time_slot text,
     status text,
     user_id bigint,
     PRIMARY KEY (group_key, day, time_slot)
   );
   CREATE TABLE group_financial_data (
     group_key text PRIMARY KEY,
     salary_option integer,
     salary numeric DEFAULT 0,
     cash numeric DEFAULT 0,
     message_id integer
   );

   INSERT INTO group_financial_data (group_key, salary_option, salary, cash, message_id) VALUES
   ('Royal_1',1,0,0,NULL),
   ('Royal_2',1,0,0,NULL),
   ('Royal_3',1,0,0,NULL),
   ('Royal_4',1,0,0,NULL),
   ('Royal_5',1,0,0,NULL),
   ('Royal_6',1,0,0,NULL);
   ```
6. **Запустить бота**:
   ```
   source .venv/bin/activate
   export BOT_TOKEN="..."
   export DATABASE_URL="..."
   export ADMIN_IDS="..."
   export BOOKING_REPORT_GROUP_ID="..."
   export FINANCIAL_REPORT_GROUP_ID="..."
   python main.py
   ```

После успешного старта в логах будет:
```
INFO __main__: Запуск приложения...
INFO root: Подключение к PostgreSQL установлено.
INFO handlers.salary: Salary settings loaded from DB.
INFO aiogram.dispatcher: Run polling for bot @YourBot
```

## 5. Рекомендации по расширению

- **Добавить новые языки**: доп. коды в `handlers/language.LANGUAGES` и `TRANSLATIONS`.
- **Добавить новые группы**: расширить `constants/booking_const.groups_data` и выполнить INSERT в `group_financial_data`.
- **Корректировка выплат**: изменить `constants/salary.salary_options`.
- **Новые статусы брони**: добавить в `status_mapping` и корректировать логику оплаты.
- **Мониторинг ошибок**: интеграция с Sentry или другими сервисами для отслеживания исключений.
- **Обновление Aiogram**: проверять совместимость при изменениях API.

"""
