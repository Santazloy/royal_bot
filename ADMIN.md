# User Guide for Royal Bot (Button-Only Instructions)

## 1. Запуск и первое взаимодействие

* После добавления бота в чат отправьте в поле ввода слово **Start** (обычно отображается как кнопка «Start»). Бот ответит приветственным сообщением и автоматически отобразит главное меню (фото + кнопки).
* Если у вас ещё нет эмодзи, бот вместо меню покажет уведомление для администраторов с запросом назначения эмодзи, а вам — сообщение с кнопкой ожидания:

  > Ожидайте — ваш аккаунт отправлен на рассмотрение администратору.
* Как только администратор назначит эмодзи, вы увидите главное меню с кнопками.

## 2. Главное меню пользователя

После получения эмодзи бот автоматически отобразит главное меню, содержащее фото и следующие кнопки:

1. **🅱️ Бронирование**
2. **📆 Расписание**
3. **🧧 Баланс**
4. **❌ Отмена брони**
5. **🇷🇺🇨🇳🇺🇸 Сменить язык**

Каждую клавишу можно нажать, чтобы перейти к соответствующему разделу:

### 2.1. Кнопка 🅱️ Бронирование

Нажмите на кнопку **🅱️ Бронирование**:

* Бот удалит текущее меню и покажет сообщение с фотографией группы (GROUP\_CHOICE\_IMG) и кнопками с названиями всех доступных групп (по 3 кнопки в ряд). Например:

  ```
  [Royal_1] [Royal_2] [Royal_3]
  [Royal_4] [Royal_5] [Royal_6]
  ```
* Затем, после выбора группы, появится новая клавиатура:

  ```
  [Сегодня] [Завтра]  [« Назад]
  ```
* Нажмите **Сегодня** или **Завтра**. Бот покажет фотографию выбора времени (TIME\_CHOICE\_IMG) и список доступных слотов (по 4 в ряд). Например:

  ```
  [09:00] [09:30] [10:00] [10:30]
  [11:00] [11:30] [12:00] [12:30]
  …
  [« Назад]
  ```
* Нажмите на свободный слот (например, **19:00**). Бот завершит бронирование и отправит сообщение:

  > 🎉 {ВашеИмя}, вы забронировали слот на 19:00 (Сегодня) в группе Royal\_1

### 2.2. Кнопка 📆 Расписание

* Нажмите на кнопку **📆 Расписание**.
* Бот отредактирует текущее сообщение и покажет отчет для обоих дней. Пример:

  ```
  📅 Все бронирования на Сегодня:
  ╔══════════╦════════════════════╗
  ║ Группа   ║ Время бронирования ║
  ╠══════════╬════════════════════╣
  ║ Royal_1  ║ 19:00   🏀         ║
  ║ Royal_2  ║ 20:30   🏈         ║
  ╚══════════╩════════════════════╝

  📅 Все бронирования на Завтра:
  ╔══════════╦════════════════════╗
  ║ Группа   ║ Время бронирования ║
  ╠══════════╬════════════════════╣
  ║ Royal_3  ║ 18:30   ⚽️         ║
  ╚══════════╩════════════════════╝
  ```
* Если вы хотите вернуть основное меню, нажмите кнопку **«Назад»** (отображается внизу клавиатуры).

### 2.3. Кнопка 🧧 Баланс

* Нажмите на кнопку **🧧 Баланс**.
* Бот отправит сообщение с вашим текущим балансом:

  > Ваш баланс: 1200¥
* Чтобы вернуться к главному меню, нажмите **«Назад»**, если такая кнопка доступна.

### 2.4. Кнопка ❌ Отмена брони

* Нажмите на кнопку **❌ Отмена брони**.
* Бот покажет список ваших активных бронирований в виде кнопок:

  ```
  [Royal_1 | Сегодня | 19:00]
  [Royal_2 | Завтра | 20:30]
  ```
* Нажмите на ту кнопку (бронь), которую вы хотите отменить.
* Бот удалит бронь, обновит календарь слотов и сообщит:

  > Бронирование отменено.
* После отмены можно нажать **«Назад»** (если доступно) для возврата к главному меню.

### 2.5. Кнопка 🇷🇺🇨🇳🇺🇸 Сменить язык

* Нажмите кнопку **🇷🇺🇨🇳🇺🇸** в правом нижнем углу меню.
* Бот отобразит клавиатуру с тремя кнопками:

  ```
  [English] [Русский] [中文]
  ```
* Нажмите на нужный язык. Бот подтвердит изменение:

  > Язык установлен на {lang\_name}.
* После подтверждения вы автоматически вернетесь к предыдущему экрану.

## 3. Особенности использования кнопочных меню

1. **Возврат в главное меню**

   * Почти на каждом экране есть кнопка **«Назад»**, которая возвращает вас к предыдущему экрану или к главному меню.
2. **Недоступные слоты**

   * Когда бот показывает список времени, забронированные и соседние слоты автоматически исчезают из клавиатуры.
   * Вы не можете нажать на недоступный слот.
3. **Уведомления в личный чат**

   * Бронирование подтверждается внутри того же чата, где вы взаимодействовали с меню, и не используется отдельная команда.
   * Отчёт о бронировании также отправляется в чат отчётов (не пользователю).
4. **Баланс и уведомления**

   * Все изменения баланса отображаются кнопкой **Баланс**.
   * При любых изменениях (оплата, списание) бот отправит личное сообщение с информацией.

## 4. Ответы на распространённые вопросы (по кнопкам)

1. **Как начать бронировать без ввода команды?**

   * Достаточно нажать кнопку **🅱️ Бронирование** из главного меню.
2. **Что делать, если не вижу кнопку «Бронирование»?**

   * Убедитесь, что вы получили эмодзи. Если меню не отображается, нажмите «Start».
3. **Как выбрать другой день?**

   * На экране выбора дня нажмите кнопку **«Назад»**, затем заново откройте **🅱️ Бронирование**.
4. **Где информация о свободных слотах?**

   * Бот автоматически показывает только доступные слоты. Нажмите кнопку с нужным временем.
5. **Как отменить бронь без ввода команды?**

   * Нажмите **❌ Отмена брони** и выберите нужный слот из списка кнопок.
6. **Как сменить язык?**

   * Нажмите кнопку **🇷🇺🇨🇳🇺🇸**, выберите нужный язык.

---

# Admin Menu Guide for Royal Bot (Deep Button-Only Instructions)

## 1. Запуск админ-меню

* Только администраторы (ID из списка `ADMIN_IDS` в `config.py`) могут получить доступ к админ-меню.
* Администратор отправляет команду `/ad`.
* Бот отправляет сообщение с фото и главными кнопками админ-меню:

  ```
  [🐆 Леонард] [💰 Зарплата]
  [😊 Эмодзи] [💵 Деньги]
  [❌ Отмена брони] [🧹 Очистка]
  [📊 Балансы] [📜 Правила]
  [🔄 Конвертация] [🔁 Сброс дня]
  [🔙 « Назад]
  ```
* Каждая кнопка запускает соответствующий сценарий. Далее подробно описан функционал для каждой.

## 2. Кнопка 🐆 Леонард

1. **Нажмите** на кнопку **🐆 Леонард**.
2. Бот вызывает `leonard_menu_callback()` из `handlers/leonard.py`.
3. **Сценарий «Леонард»** (файл `handlers/leonard.py`):

   * Отображаются кнопки для управления «Леонард»-разделом (например, просмотр статистики, настройка параметров «Леонард» и т. д.).
   * Пример возможных кнопок:

     ```
     [📊 Статистика] [⚙️ Настройки]
     [🔙 Назад]
     ```
   * При нажатии **📊 Статистика** бот собирает данные о «Леонард»-операциях (например, количество звонков, доходы и т. д.) и отправляет в сообщении табличный отчёт.
   * При нажатии **⚙️ Настройки** бот предлагает изменить параметры через далее вложенные кнопки (например, установить пороговое значение, выбрать вид отчёта) и сохраняет изменения в базе.
   * **Возврат**: при любом экране внутри «Леонард»-раздела есть кнопка **🔙 Назад**, которая возвращает к главному админ-меню.

> **Примечание**: Реальный набор кнопок и логика находится в файле `handlers/leonard.py`. Здесь описан общий принцип.

## 3. Кнопка 💰 Зарплата

### 3.1. Шаг 1: Выбор группы

1. **Нажмите** **💰 Зарплата**.
2. Бот отправляет фото (`SALARY_PHOTO`) и клавиатуру со списком групп (по 2 кнопки в ряд):

   ```
   [Royal_1] [Royal_2]
   [Royal_3] [Royal_4]
   [Royal_5] [Royal_6]
   [❌ Отменить]
   ```
3. **Нажмите** нужную группу (например, **Royal\_2**).
4. **Возврат**: кнопка **❌ Отменить** завершает сценарий и возвращает к главному админ-меню.

### 3.2. Шаг 2: Выбор опции зарплаты

1. Бот отображает ту же фотографию и клавиатуру с опциями 1–4 (по одной кнопке в строке) и кнопкой **❌ Отменить**:

   ```
   [   1]   <-- если текущая опция не равна 1
   [✅ 2]   <-- если текущая опция равна 2
   [   3]
   [   4]
   [❌ Отменить]
   ```
2. **Нажмите** на нужную опцию (например, **3**):

   * Бот обновляет `salary_option` для выбранной группы в `groups_data` и в таблице `group_financial_data`.
   * Бот отправляет подтверждающее сообщение:

     > Опция зарплаты для Royal\_2 установлена: 3.
3. **Возврат**: после выбора опции или нажатия **❌ Отменить**, бот возвращает к главному админ-меню.

### 3.3. Итоговая логика

* **salary\_command** (`/salary` или через кнопку) приводит к тому же сценарию.
* Состояние FSM **SalaryStates** очищается после выбора или отмены.

## 4. Кнопка 😊 Эмодзи

### 4.1. Шаг 1: Список пользователей

1. **Нажмите** **😊 Эмодзи**.
2. Бот загружает из базы всех пользователей (`SELECT user_id, username FROM users`) и показывает клавиатуру с кнопками:

   ```
   [user1] [user2] [user3]
   [user4] [user5] …
   ```

   * Если имя пользователя отсутствует, отображается ID.
3. **Нажмите** на нужного пользователя (например, **user4**).
4. **Возврат**: чтобы прекратить назначение, нажмите **«Назад»**, бот вернёт к главному админ-меню.

### 4.2. Шаг 2: Выбор эмодзи

1. После выбора пользователя бот отправляет фото (`STARTEMOJI_PHOTO`) и клавиатуру с эмодзи (по 5 в ряд) и полосой из 20 `CUSTOM_EMOJIS`:

   ```
   [⚽️] [🪩] [🏀] [🏈] [⚾️]
   [🥎] [🎾] [🏐] [🏉] [🎱]
   [🏓] [🏸] [🥅] [⛳️] [🪁]
   [🏒] [🏑] [🏏] [🪃] [🥍]
   [⚽️🪩🏀]
   [« Назад]
   ```

   * Первая 4 строки: 20 одиночных эмодзи.
   * Пятая строка: кнопка с тремя эмодзи `⚽️🪩🏀`.
2. **Нажмите** на единственное эмодзи, чтобы сохранить только его. Бот выполнит:

   * `INSERT` или `UPDATE` в таблицу `user_emojis` → поле `emojis` будет равно строке выбранного эмодзи.
   * Отправит подтверждающее сообщение:

     > Пользователю user4 назначен эмодзи: 🏈
   * Присвоенный эмодзи будет храниться циклически в `get_next_emoji()`.
   * Бот попытается отправить пользователю личное уведомление:

     > Вам назначен эмодзи: 🏈
     > Теперь доступны все команды!
3. **Нажмите** на кнопку **⚽️🪩🏀** (многосимвольное) для назначения сразу трёх эмодзи:

   * Бот сохранит комбинацию `['⚽️','🪩','🏀']` (в указанном порядке).
   * Сохраняет в `user_emojis` колонку `emojis = '⚽️,🪩,🏀'`.
   * Подтверждает:

     > Пользователю user4 назначены эмодзи: ⚽️🪩🏀
   * Уведомит пользователя:

     > Вам назначены эмодзи: ⚽️🪩🏀
     > Теперь доступны все команды!
4. **Возврат**: после назначения или при нажатии **«Назад»**, бот возвращает к главному админ-меню.

## 5. Кнопка 💵 Деньги

### 5.1. Шаг 1: Выбор раздела (Зарплата / Наличные)

1. **Нажмите** **💵 Деньги**.
2. Бот отобразит фото (`MONEY_PHOTO` — если задано) и клавиатуру:

   ```
   [Зарплата] [Наличные]
   [« Назад]
   ```
3. **Нажмите** **Зарплата** или **Наличные**.
4. **Возврат**: кнопка **«Назад»** возвращает к главному админ-меню.

### 5.2. Шаг 2: Выбор группы

1. Бот покажет клавиатуру с кнопками групп (по 2 в ряд) и **❌ Отменить**:

   ```
   [Royal_1] [Royal_2]
   [Royal_3] [Royal_4]
   [Royal_5] [Royal_6]
   [❌ Отменить]
   ```
2. **Нажмите** нужную группу (например, **Royal\_3**).
3. **Возврат**: **❌ Отменить** → главное админ-меню.

### 5.3. Шаг 3: Выбор операции (+ / −)

1. После выбора группы бот покажет клавиатуру:

   ```
   [➕] [➖]
   [« Назад]
   ```
2. **Нажмите** **➕** (увеличить) или **➖** (уменьшить).
3. **Возврат**: **« Назад** → предыдущий шаг (выбор раздела).

### 5.4. Шаг 4: Ввод суммы

1. Бот отправит текстовое сообщение-запрос:

   > Пожалуйста, введите сумму для группы Royal\_3:
2. **Введите** число любым текстом (например, `500`).

   * После ввода бот проверит корректность (целое число >0).
   * Если введено не число, отправит сообщение:

     > Некорректный ввод, попробуйте ещё раз.
   * Если корректно, бот обновит данные:

     * Если выбрано **Зарплата**, увеличит/уменьшит `groups_data['Royal_3']['salary']` и `group_financial_data.salary`.
     * Если **Наличные**, папдобавит/отнимет от `groups_data['Royal_3']['cash']` и `group_financial_data.cash`.
3. **Бот отправит** подтверждение:

   > Зарплата для Royal\_3 изменена на 500¥.

### 5.5. Завершение и возврат

* После успешного изменения бот возвращает к главному админ-меню.
* Для возврата без изменений используйте **« Назад** или **❌ Отменить**.

## 6. Кнопка ❌ Отмена брони (Admin Cancel Booking)

### 6.1. Просмотр всех забронированных слотов

1. **Нажмите** **❌ Отмена брони**.
2. Бот отправит фото (`PHOTO_ID`) и клавиатуру со всеми слотами, находящимися в состоянии "booked", сгруппированными по дням и группам.
3. Пример отображения кнопок (по одной кнопке на слот):

   ```
   [Royal_1 | Сегодня | 19:00]
   [Royal_2 | Сегодня | 20:00]
   [Royal_3 | Завтра  | 18:30]
   …
   [« Назад]
   ```
4. Кнопки упорядочены по алфавиту групп и времени.
5. **Возврат**: **« Назад** → главное админ-меню.

### 6.2. Выбор слота для удаления

1. **Нажмите** на кнопку, соответствующую слоту (например, **\[Royal\_2 | Сегодня | 20:00]**).
2. Бот удалит выбранный слот:

   * Удалит запись из таблицы `bookings` и `group_time_slot_statuses`.
   * Удалит слоты-соседи из `unavailable_slots`.
   * Обновит in-memory:

     * `groups_data['Royal_2']['booked_slots']['Сегодня'].remove('20:00')`
     * `time_slot_statuses` и `slot_bookers` очистятся для этого слота и соседних.
3. Бот обновит групповое сообщение (метод `update_group_message()`).
4. **Бот отправит** подтверждение:

   > Слот отменён.
5. **Возврат**: автоматически перейдёт к списку слотов (обновленному). Для возврата в главное админ-меню нажмите **« Назад**.

## 7. Кнопка 🧹 Очистка (Clean)

### 7.1. Шаг 1: Выбор типа данных для очистки

1. **Нажмите** **🧹 Очистка**.
2. Бот отправляет фото (`CLEAN_PHOTO` — если задано) и клавиатуру с четырьмя кнопками:

   ```
   [Time] [Salary]
   [Cash] [All]
   [« Назад]
   ```
3. **Time** — очистка всех временных данных (таблицы `bookings` и `group_time_slot_statuses`).
4. **Salary** — сброс зарплаты до 0.
5. **Cash** — сброс наличных до 0.
6. **All** — очистка всех данных (Time, Salary, Cash).
7. **Возврат**: **« Назад** → главное админ-меню.

### 7.2. Шаг 2: Выбор группы или «All»

1. После выбора раздела (например, **Salary**) бот отобразит клавиатуру:

   ```
   [Royal_1] [Royal_2]
   [Royal_3] [Royal_4]
   [Royal_5] [Royal_6]
   [All] [❌ Отменить]
   ```
2. **Нажмите** кнопку группы (например, **Royal\_4**) или **All**.
3. **Возврат**: **❌ Отменить** → начало сценария очистки.

### 7.3. Шаг 3: Подтверждение очистки

1. Бот спросит подтверждение:

   ```
   [Да, стереть] [❌ Отменить]
   ```
2. **Нажмите** **Да, стереть**:

   * Если выбран **Time**, бот удалит все записи `bookings` и `group_time_slot_statuses` для указанной группы (или всех групп) в БД, очистит in-memory структуры:

     * `groups_data[gk]['booked_slots'] = {'Сегодня': [], 'Завтра': []}`
     * `groups_data[gk]['time_slot_statuses'] = {}`, `slot_bookers`, `unavailable_slots` — очищаются.
     * Вызовет `update_group_message()` → обновит групповое сообщение (оставит пустой список слотов).
   * Если выбран **Salary**, сбросит `groups_data[gk]['salary'] = 0` и в таблице `group_financial_data.salary = 0`.
   * Если выбран **Cash**, сбросит `groups_data[gk]['cash'] = 0` и в БД `group_financial_data.cash = 0`.
   * Если выбран **All**, выполнит все три очистки последовательно для указанной группы или всех.
3. Бот отправит подтверждение:

   > Данные "{section}" стерты для {Royal\_X/всех групп}.
4. **Возврат**: бот возвращается к главному админ-меню.
5. **Отмена**: при нажатии **❌ Отменить** на любом шаге — бот возвращает к главному админ-меню без изменений.

## 8. Кнопка 📊 Балансы (User Balances)

1. **Нажмите** **📊 Балансы**.
2. Бот отправит сообщение, содержащее список всех пользователей и их баланс:

   ```
   1. 🏀 user1: 1200¥
   2. 🏈 user2: 800¥
   3. 🏉 user3: 1500¥
   …
   ```
3. Пользователи сортируются по `user_id` в порядке возрастания.
4. **Возврат**: нажмите **« Назад»**, чтобы вернуться к главному админ-меню.

## 9. Кнопка 📜 Правила (Rules)

1. **Нажмите** **📜 Правила**.
2. Бот ответит:

   > Не реализовано
3. **Возврат**: нажмите **« Назад»**, чтобы вернуться к главному админ-меню.

## 10. Кнопка 🔄 Конвертация (Conversion)

1. **Нажмите** **🔄 Конвертация**.
2. Бот ответит:

   > Не реализовано
3. **Возврат**: нажмите **« Назад»**, чтобы вернуться к главному админ-меню.

## 11. Кнопка 🔁 Сброс дня (Reset Day)

1. **Нажмите** **🔁 Сброс дня**.
2. Бот выполнит функцию `do_next_core()` из `handlers/next.py`:

   1. Соберёт отчёт по всем группам за "Сегодня" и отправит в `FINANCIAL_REPORT_GROUP_ID`, включающий:

      * Количество бронирований.
      * Суммы по методам оплаты (наличные, безнал, агент).
      * Список пользователей с количеством бронирований и их вкладом.
   2. Удалит все записи с `day = 'Сегодня'` из таблиц `bookings` и `group_time_slot_statuses`.
   3. Очистит in-memory для "Сегодня":

      * `booked_slots['Сегодня'] = []`
      * `time_slot_statuses` и `slot_bookers` очищаются для записей с "Сегодня".
      * `unavailable_slots['Сегодня'] = set()`.
   4. Перенесёт записи с "Завтра" во все структуры:

      * В БД: `UPDATE bookings SET day='Сегодня' WHERE day='Завтра'` и аналогично для `group_time_slot_statuses`.
      * В in-memory: скопирует `booked_slots['Завтра']` → `booked_slots['Сегодня']`, очистит `Завтра`.
      * Сдвинет `time_slot_statuses` и `slot_bookers` для записей "Завтра" в "Сегодня".
   5. Для каждой группы вызовет `update_group_message()` → обновит групповое сообщение текущим состоянием.
3. Бот отправит всплывающее уведомление:

   > ✅ Отчет сформирован, бронирования перенесены.
4. **Возврат**: бот остаётся в админ-меню (с возможностью повторного сброса) или можно нажать **« Назад»** для выхода.

## 12. Кнопка 🔙 « Назад

1. **Нажмите** **🔙 « Назад**.
2. Бот удалит текущее сообщение админ-меню (если возможно) и завершит FSM, возвращая админа к состоянию без активных клавиатур.

## 13. Особенности и исключения

1. **Проверка прав**:

   * Если невостребованный пользователь нажимает кнопку (не в `ADMIN_IDS`), бот покажет всплывающее сообщение:

     > Только для админов!
   * Этот текст соответствует переводу ключа `admin_only` из `handlers/language.py`.
2. **Обработка ошибок**:

   * При любых ошибках взаимодействия бот выводит лог в консоль и не крашится.
   * При сбоях в БД бот возвращает сообщение об ошибке и остаётся в том же меню.
3. **Интерактивное обновление**:

   * После каждого действия бот обновляет сообщение клавиатурой или текстом, обеспечивая «живой» интерфейс.
4. **Без использования слеш-команд**:

   * Все действия выполняются исключительно кнопками. Слеш-команды, кроме `/ad`, не используются.

---

*Глубокая инструкция для администраторов, описывающая каждую кнопку админ-меню и все последующие уровни управления.*
