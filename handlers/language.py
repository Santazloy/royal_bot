# handlers/language.py

from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import db

language_router = Router()

LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
    'zh': '中文',
}

TRANSLATIONS = {
    # --- КЛЮЧИ ДЛЯ /menu (ПОЛЬЗОВАТЕЛЬСКОЕ МЕНЮ) ---
    'menu_btn_booking': {
        'en': '🅱️Booking',
        'ru': '🅱️Бронирование',
        'zh': '🅱️预订',
    },
    'menu_btn_girls': {
        'en': '👯‍♀️Girls',
        'ru': '👯‍♀️Девушки',
        'zh': '👯‍♀️女士',
    },
    'menu_btn_schedule': {
        'en': '📆Schedule',
        'ru': '📆Расписание',
        'zh': '📆日程',
    },
    'menu_btn_balance': {
        'en': '🧧Balance',
        'ru': '🧧Баланс',
        'zh': '🧧余额',
    },
    'menu_btn_news': {
        'en': '📰News',
        'ru': '📰Новости',
        'zh': '📰新闻',
    },
    'menu_btn_cancel_booking': {
        'en': '❌Cancel booking',
        'ru': '❌Отмена брони',
        'zh': '❌取消预订',
    },
    'menu_no_action': {
        'en': 'No action for this button.',
        'ru': 'Нет действия для этой кнопки.',
        'zh': '此按钮暂无操作。',
    },
    'menu_news_header': {
        'en': 'Latest news:',
        'ru': 'Последние новости:',
        'zh': '最新新闻：',
    },

    # Общие сообщения
    'no_action': {
        'en': 'Button without action.',
        'ru': 'Просто заглушка-кнопка без действия.',
        'zh': '仅作占位的按钮，无操作。',
    },
    'invalid_data': {
        'en': 'Invalid data.',
        'ru': 'Некорректные данные.',
        'zh': '数据无效。',
    },
    'no_such_group': {
        'en': 'No such group!',
        'ru': 'Нет такой группы!',
        'zh': '未找到此组！',
    },
    'no_such_booking': {
        'en': 'No such booking.',
        'ru': 'Нет такой брони.',
        'zh': '未找到该预订。',
    },
    'no_permission': {
        'en': 'You do not have permission to perform this action.',
        'ru': 'У вас нет прав для выполнения этого действия.',
        'zh': '您没有权限执行此操作。',
    },
    'admin_only': {
        'en': 'Admin only!',
        'ru': 'Только для админов!',
        'zh': '仅限管理员!',
    },
    'incorrect_input': {
        'en': 'Incorrect input, please try again.',
        'ru': 'Некорректный ввод, попробуйте ещё раз.',
        'zh': '输入有误，请重试。',
    },
    'incorrect_number': {
        'en': 'Incorrect input number!',
        'ru': 'Неверный ввод числа!',
        'zh': '数字输入有误！',
    },
    'invalid_amount': {
        'en': 'Invalid amount.',
        'ru': 'Неверная сумма.',
        'zh': '金额无效。',
    },
    'distribution_message': {
        'en': 'Credited {amount}, balance {balance}',
        'ru': 'Начислено {amount}, баланс {balance}',
        'zh': '已到账{amount}，余额{balance}',
    },
    'cancelled': {
        'en': 'Cancelled.',
        'ru': 'Отменено.',
        'zh': '已取消。',
    },

    # Бронирование
    'choose_time_styled': {
        'en': 'Please choose a time on {day}',
        'ru': 'Пожалуйста, выберите время на {day}',
        'zh': '请选择{day}的时间',
    },
    'today': {
        'en': 'Today',
        'ru': 'Сегодня',
        'zh': '今天',
    },
    'tomorrow': {
        'en': 'Tomorrow',
        'ru': 'Завтра',
        'zh': '明天',
    },
    'slot_booked': {
        'en': 'You have booked a slot at {time} ({day}) in group {group}',
        'ru': 'Вы забронировали слот на {time} ({day}) в группе {group}',
        'zh': '您已在{day}{time}预订了组{group}的时段',
    },
    'all_bookings_title': {
        'en': 'All bookings on {day}',
        'ru': 'Все бронирования на {day}',
        'zh': '{day}的所有预订',
    },
    'no_active_bookings': {
        'en': 'No active bookings.',
        'ru': 'Нет активных бронирований.',
        'zh': '没有活跃的预订。',
    },
    'no_bookings': {
        'en': 'No bookings.',
        'ru': 'Нет бронирований.',
        'zh': '没有预订。',
    },
    'off_choose_booking': {
        'en': 'Choose a booking to cancel',
        'ru': 'Выберите бронирование для отмены',
        'zh': '选择要取消的预订',
    },
    'booking_cancelled': {
        'en': 'Booking cancelled.',
        'ru': 'Бронирование отменено.',
        'zh': '预订已取消。',
    },
    'booking_cancelled_by_admin': {
        'en': 'Booking cancelled by admin.',
        'ru': 'Бронирование отменено администратором.',
        'zh': '管理员已取消预订。',
    },

    # Оплата
    'select_method_payment': {
        'en': 'Select payment method:',
        'ru': 'Выберите способ оплаты:',
        'zh': '选择付款方式：',
    },
    'enter_payment_amount': {
        'en': 'Please enter the payment amount:',
        'ru': 'Пожалуйста, введите сумму оплаты:',
        'zh': '请输入付款金额：',
    },
    'changed_balance_user': {
        'en': 'Your balance has changed: {op}{amount}. Current balance: {balance}',
        'ru': 'Ваш баланс изменён: {op}{amount}. Текущий баланс: {balance}',
        'zh': '您的余额已更改：{op}{amount}。当前余额：{balance}',
    },
    'payment_ack_agent': {
        'en': 'Payment (agent) recorded.',
        'ru': 'Оплата (agent) учтена.',
        'zh': '付款（代理）已记录。',
    },
    'payment_confirmation': {
        'en': 'Payment of {amt} ({method}) recorded, status={emoji}.',
        'ru': 'Учли оплату {amt} (метод={method}), статус={emoji}.',
        'zh': '已记录 {amt}（{method}）的付款，状态={emoji}。',
    },

    # Языки
    'help_lang': {
        'en': 'Select your language',
        'ru': 'Выберите язык',
        'zh': '选择语言',
    },
    'lang_set_success': {
        'en': 'Language set to {lang_name}.',
        'ru': 'Язык установлен на {lang_name}.',
        'zh': '语言已设置为 {lang_name}。',
    },

    # Кнопки (основные)
    'btn_cash':            {'en': 'Cash',            'ru': 'Наличные',      'zh': '现金'},
    'btn_beznal':          {'en': 'Cashless',        'ru': 'Безнал',        'zh': '非现金'},
    'btn_agent':           {'en': 'Agent',           'ru': 'Агент',         'zh': '代理'},
    'btn_back':            {'en': '« Back',          'ru': '« Назад',       'zh': '« 返回'},
    'btn_cancel':          {'en': '❌❌❌ Cancel',     'ru': '❌❌❌ Отменить', 'zh': '❌❌❌ 取消'},
    'btn_booking':         {'en': '⏰ Booking',       'ru': '⏰ Бронирование','zh': '⏰ 预订'},
    'btn_girls':           {'en': '💃 Girls',        'ru': '💃 Девушки',     'zh': '💃 女士'},
    'btn_schedule':        {'en': '📋 Schedule',     'ru': '📋 Расписание',  'zh': '📋 日程'},
    'btn_balance':         {'en': '🧮 Balance',      'ru': '🧮 Баланс',      'zh': '🧮 余额'},
    'btn_news':            {'en': 'News',            'ru': 'Новости',       'zh': '新闻'},
    'btn_cancel_booking':  {'en': 'Cancel booking',  'ru': 'Отмена брони',   'zh': '取消预订'},
    'btn_photo_id':        {'en': 'Photo ID',        'ru': 'Айди фото',      'zh': '图片ID'},
    'btn_group_id':        {'en': 'Group ID',        'ru': 'Айди группы',    'zh': '群组ID'},
    'btn_salary':          {'en': 'Salary',          'ru': 'Зарплата',       'zh': '工资'},
    'btn_ai_models':       {'en': 'AI Models',       'ru': 'Модели ИИ',      'zh': 'ИИ 模型'},
    'btn_emoji':           {'en': 'Emoji',           'ru': 'Эмодзи',         'zh': '表情'},
    'btn_money':           {'en': 'Money',           'ru': 'Деньги',         'zh': '资金'},
    'btn_balances':        {'en': 'Balances',        'ru': 'Балансы',        'zh': '余额'},
    'btn_rules':           {'en': 'Rules',           'ru': 'Правила',        'zh': '规则'},
    'btn_embedding':       {'en': 'Embedding',       'ru': 'Эмбеддинг',      'zh': '嵌入'},
    'btn_conversion':      {'en': 'Conversion',      'ru': 'Конвертация',    'zh': '转换'},
    'btn_reset_day':       {'en': 'Reset Day',       'ru': 'Сброс дня',      'zh': '重置天'},
    'btn_users':           {'en': 'Users',           'ru': 'Пользователи',   'zh': '用户'},
    'btn_clean':           {'en': 'Clean',           'ru': 'Очистка',        'zh': '清理'},

    # Админ-меню, заголовки, секции
    'menu_admin_header':     {'en': 'Admin menu:',          'ru': 'Меню администратора:',       'zh': '管理员菜单：'},
    'menu_users_header':     {'en': 'User management',       'ru': 'Управление пользователями',  'zh': '用户管理'},
    'menu_balances_header':  {'en': 'Balances',              'ru': 'Балансы',                 'zh': '余额'},
    'menu_conversion_header':{'en': 'Conversion',            'ru': 'Конвертация',             'zh': '转换'},
    'menu_embedding_header': {'en': 'Embedding',             'ru': 'Эмбеддинг',               'zh': '嵌入'},
    'menu_reset_day_header': {'en': 'Reset Day',             'ru': 'Сброс дня',               'zh': '重置天'},
    'menu_emoji_header':     {'en': 'Emoji management',      'ru': 'Управление эмодзи',       'zh': '表情管理'},
    'menu_ai_models_header': {'en': 'AI Models',            'ru': 'Модели ИИ',              'zh': 'ИИ 模型'},
    'menu_rules_header':     {'en': 'Rules',                 'ru': 'Правила',                'zh': '规则'},
    'menu_photo_id_header':  {'en': 'Photo ID management',   'ru': 'Управление фото ID',      'zh': '图片ID管理'},
    'menu_group_id_header':  {'en': 'Group ID management',   'ru': 'Управление группами',     'zh': '群组ID管理'},
    'menu_back_confirm':     {'en': 'Exit from admin menu.', 'ru': 'Выход из админ-меню.',     'zh': '退出管理员菜单。'},
    'menu_unknown_command':  {'en': 'Unknown command.',      'ru': 'Неизвестная команда.',    'zh': '未知的命令。'},
    'menu_unknown':          {'en': 'Unknown menu action!',  'ru': 'Неизвестная команда меню!', 'zh': '未知的菜单操作！'},

    # Новости
    'news_header':          {'en': 'Latest news:',           'ru': 'Последние новости:',       'zh': '最新新闻：'},
    'btn_add':              {'en': 'Add',                     'ru': 'Добавить',                 'zh': '添加'},
    'btn_edit':             {'en': 'Edit',                    'ru': 'Редактировать',            'zh': '编辑'},
    'btn_delete':           {'en': 'Delete',                  'ru': 'Удалить',                  'zh': '删除'},
    'news_manage':          {'en': 'Manage news:',            'ru': 'Управление новостями:',    'zh': '管理新闻：'},
    'news_none':            {'en': 'No news yet.',            'ru': 'Пока нет новостей.',       'zh': '暂时没有新闻。'},
    'news_no_text':         {'en': '(no text)',              'ru': '(без текста)',            'zh': '(无文本)'},
    'news_item':            {'en': '📰 ID={id}: {text}',      'ru': '📰 ID={id}: {text}',       'zh': '📰 ID={id}：{text}'},
    'news_photos_prompt':   {'en': 'Attach up to 10 photos for the news.',
                             'ru': 'Прикрепите до 10 фото для новости.',
                             'zh': '为新闻附上最多10张图片。'},
    'news_photo_received':  {'en': 'Photo received.',         'ru': 'Фото получено.',          'zh': '已收到图片。'},
    'news_photo_limit':     {'en': 'Photo limit reached.',    'ru': 'Достигнут лимит фото.',    'zh': '已达图片数量上限。'},
    'news_no_photos':       {'en': 'No photos attached.',     'ru': 'Нет прикреплённых фото.',  'zh': '未附加图片。'},
    'news_deleted_all':     {'en': 'All news deleted.',       'ru': 'Все новости удалены.',     'zh': '所有新闻已删除。'},
    'news_edit_prompt':     {'en': 'Send the new text for the news:',
                             'ru': 'Отправьте новый текст для новости:',
                             'zh': '发送新闻的新文本：'},
    'done':                 {'en': 'Operation completed. Data updated.',
                             'ru': 'Операция завершена. Данные обновлены.',
                             'zh': '操作完成。数据已更新。'},

    # Очистка (clean)
    'clean_time':                   {'en': 'Time',                         'ru': 'Время',                     'zh': '时间'},
    'clean_salary':                 {'en': 'Salary',                       'ru': 'Зарплата',                   'zh': '工资'},
    'clean_cash':                   {'en': 'Cash',                         'ru': 'Наличные',                   'zh': '现金'},
    'clean_all':                    {'en': 'Clear all data',               'ru': 'Стереть все данные',         'zh': '清除所有数据'},
    'clean_prompt':                 {'en': 'What would you like to clear?',
                                     'ru': 'Что вы хотите стереть?',             'zh': '您想清除什么？'},
    'clean_confirm_all':            {'en': 'Yes, clear all',               'ru': 'Да, стереть все данные',     'zh': '是的，全部清除'},
    'clean_confirm_all_prompt':     {'en': 'Confirm clearing ALL data (time/salary/cash) for ALL groups?',
                                     'ru': 'Подтвердите удаление ВСЕХ данных (время/зарплата/наличные) по ВСЕМ группам?',
                                     'zh': '确认清除所有群组的所有数据（时间/工资/现金）？'},
    'clean_section_prompt':         {'en': 'You chose: {section}\nSelect a group or "Clear all {section}"',
                                     'ru': 'Вы выбрали: {section}\nВыберите группу или «Стереть все {section}»',
                                     'zh': '您已选择：{section}\n请选择一个群组或“清除所有{section}”'},
    'clean_confirm_section_prompt': {'en': 'Confirm clearing {section} for ALL groups?',
                                     'ru': 'Подтвердите удаление {section} по ВСЕМ группам?',
                                     'zh': '确认清除所有群组的{section}？'},
    'clean_confirm_group':          {'en': 'Yes, clear',                   'ru': 'Да, стереть!',             'zh': '是的，清除！'},
    'clean_group_prompt':           {'en': 'Confirm clearing {section} for group {group}',
                                     'ru': 'Подтвердите удаление {section} для группы {group}',
                                     'zh': '确认清除群组{group}的{section}？'},
    'clean_done_all':               {'en': 'Cleared all {section} for all groups.',
                                     'ru': 'Все данные «{section}» стёрты для всех групп.',
                                     'zh': '已为所有群组清除所有{section}。'},
    'clean_done_group':             {'en': 'Cleared {section} for group {group}.',
                                     'ru': 'Данные «{section}» стёрты для группы {group}.',
                                     'zh': '已为群组{group}清除{section}。'},

    # Финансы/деньги (money)
    'choose_what_change':    {'en': 'What do you want to change?',     'ru': 'Что вы хотите изменить?',        'zh': '您想要修改什么？'},
    'select_operation':      {'en': 'Select operation:',                'ru': 'Выберите операцию:',               'zh': '请选择操作：'},
    'enter_amount':          {'en': 'Enter the amount:',                'ru': 'Введите сумму:',                   'zh': '请输入金额：'},
    'salary':                {'en': 'Salary',                            'ru': 'Зарплата',                        'zh': '工资'},
    'cash':                  {'en': 'Cash',                              'ru': 'Наличные',                        'zh': '现金'},
    'plus':                  {'en': '➕',                                 'ru': '➕',                                'zh': '➕'},
    'minus':                 {'en': '➖',                                 'ru': '➖',                                'zh': '➖'},
    'money_choose_type':     {'en': 'Select operation type:',            'ru': 'Выберите тип операции:',              'zh': '请选择操作类型：'},
    'money_choose_group':    {'en': 'Select a group:',                   'ru': 'Выберите группу:',                  'zh': '请选择群组：'},
    'money_choose_op':       {'en': 'Select operation for group {group}:', 'ru': 'Выберите операцию для группы {group}:', 'zh': '请选择群组 {group} 的操作：'},
    'money_amount_prompt':   {'en': 'Please enter the amount for group {group}:',
                              'ru': 'Введите сумму для группы {group}:',
                              'zh': '请输入群组 {group} 的金额：'},

    # Salary admin
    'salary_choose_group':   {'en': 'Choose a group to configure salary:',
                              'ru': 'Выберите группу для настройки зарплаты:',
                              'zh': '请选择要配置工资的组：'},
    'salary_option_prompt':  {'en': 'Group: <b>{group}</b>\nCurrent option: <b>{current}</b>\nSelect a new one:',
                              'ru': 'Группа: <b>{group}</b>\nТекущая опция: <b>{current}</b>\nВыберите новую:',
                              'zh': '组：<b>{group}</b>\n当前选项：<b>{current}</b>\n请选择新的：'},
    'salary_set':           {'en': 'Salary option for {group} set to {opt}.',
                              'ru': 'Опция зарплаты для {group} установлена: {opt}.',
                              'zh': '已为组{group}设置工资选项：{opt}。'},

    # ID Photo
    'photo_id':             {'en': 'file_id of your photo:\n<code>{file_id}</code>',
                              'ru': 'file_id вашего фото:\n<code>{file_id}</code>',
                              'zh': '您照片的 file_id：\n<code>{file_id}</code>'},
    'no_photo':             {'en': 'You did not attach a photo to the /id command.',
                              'ru': 'Вы не прикрепили фото к команде /id.',
                              'zh': '您未在 /id 命令中附加图片。'},

    # Emoji
    'emoji_choose_user':     {'en': 'Select a user:',                  'ru': 'Выберите пользователя:',        'zh': '选择用户：'},
    'emoji_choose_emoji':    {'en': 'Select emoji for user {target_id}:',
                              'ru': 'Выберите эмоджи для пользователя {target_id}:',
                              'zh': '为用户 {target_id} 选择表情：'},
    'emoji_assigned':        {'en': 'Emoji assigned to user {target_id}: {emoji}',
                              'ru': 'Пользователю {target_id} присвоен эмоджи: {emoji}',
                              'zh': '用户 {target_id} 已分配表情：{emoji}'},
    'emoji_incorrect':       {'en': 'Incorrect user_id!',              'ru': 'Некорректный user_id!',         'zh': 'user_id 错误！'},
    'emoji_data_error':      {'en': 'Data error',                      'ru': 'Ошибка данных',                 'zh': '数据错误'},
    'emoji_notify':          {'en': 'You have been assigned emoji: {emoji}\nAll commands are now available!',
                              'ru': 'Вам назначен эмоджи: {emoji}\nТеперь доступны все команды!',
                              'zh': '您已分配表情：{emoji}\n现在所有命令均可用！'},

    # AI
    'openai_not_set':        {'en': '❌ OpenAI API key is not set.',      'ru': '❌ OpenAI API key не задан.',            'zh': '❌ OpenAI API 密钥未设置。'},
    'openai_models_none':    {'en': '⚠️ No available models found.',      'ru': '⚠️ Не найдено доступных моделей.',       'zh': '⚠️ 未找到可用模型。'},
    'openai_models_header':  {'en': '✅ Available OpenAI models:\n{text}',
                              'ru': '✅ Доступні модели OpenAI:\n{text}',
                              'zh': '✅ 可用 OpenAI 模型：\n{text}'},
    'openai_error':          {'en': '🚨 Error getting models: {e}',      'ru': '🚨 Помилка при отриманні моделей: {e}',  'zh': '🚨 获取模型出错：{e}'},

    # Баланс и прочее
    'db_not_initialized':   {'en': 'Database is not initialized.',     'ru': 'База данных не инициализирована.',  'zh': '数据库未初始化。'},

    # Дополнительные сервисные сообщения
    'btn_group_id_raw':     {'en': '💬 Group ID',         'ru': '💬 ID группы',        'zh': '💬 群组ID'},
    'btn_photo_id_raw':     {'en': '📷 Photo ID',         'ru': '📷 ID фото',         'zh': '📷 图片ID'},
    'btn_ai_models_raw':    {'en': '🦾 AI Models',        'ru': '🦾 Модели ИИ',        'zh': '🦾 ИИ 模型'},
    'btn_embeddings_raw':   {'en': '🗃 Embeddings',       'ru': '🗃 Эмбеддинги',       'zh': '🗃 嵌入'},
    'btn_report_raw':       {'en': '🧾 Report',           'ru': '🧾 Отчет',           'zh': '🧾 报告'},
    'btn_back_raw':         {'en': '🔙 Back',             'ru': '🔙 Назад',           'zh': '🔙 返回'},

    # User-flow и другие уточнённые строки
    'only_admin':           {'en': 'Admin only!',                     'ru': 'Только админ!',                    'zh': '仅限管理员！'},
    'no_rights':            {'en': 'No rights!',                       'ru': 'Нет прав!',                        'zh': '无权限！'},
    'new_user':             {'en': 'New user',                         'ru': 'Новый пользователь',               'zh': '新用户'},
    'enter_number_cancel':  {'en': 'You must enter a number. /cancel to abort.',
                              'ru': 'Нужно ввести число. /cancel для отмены.',
                              'zh': '需要输入数字。发送 /cancel 取消。'},
    'assign_emoji':         {'en': 'Assign emoji',                     'ru': 'Назначить эмодзи',                 'zh': '分配表情'},
    'change_name':          {'en': 'Change name',                      'ru': 'Изм. имя',                         'zh': '修改名字'},
    'change_emoji':         {'en': 'Change emoji',                     'ru': 'Изм. эмодзи',                      'zh': '修改表情'},
    'change_balance':       {'en': 'Change balance',                   'ru': 'Изм. баланс',                      'zh': '修改余额'},
    'user_added':           {'en': 'User {new_id} added (name and emoji not set yet).',
                              'ru': 'Пользователь {new_id} добавлен (имя и эмодзи пока не заданы).',
                              'zh': '用户 {new_id} 已添加（姓名和表情尚未设置）。'},
    'username_updated':     {'en': 'Username {user_id_} updated: {new_name}',
                              'ru': 'Имя пользователя {user_id_} обновлено: {new_name}',
                              'zh': '用户名 {user_id_} 已更新：{new_name}'},
    'emoji_updated':        {'en': 'Emoji for {user_id_} updated: {new_emoji_str}',
                              'ru': 'Эмодзи для {user_id_} обновлено: {new_emoji_str}',
                              'zh': '用户 {user_id_} 的表情已更新：{new_emoji_str}'},
    'balance_user_changed': {'en': 'User {user_id_} balance changed ({op_text}{amount}), new: {new_balance}',
                              'ru': 'Баланс пользователя {user_id_} изменён ({op_text}{amount}), итог: {new_balance}¥',
                              'zh': '用户 {user_id_} 余额已更改（{op_text}{amount}），新余额：{new_balance}¥'},
    'agent_label':          {'en': 'agent',                            'ru': 'агент',                              'zh': '代理'},
    'cash_label':           {'en': 'cash',                             'ru': 'наличные',                           'zh': '现金'},
    'cashless_label':       {'en': 'cashless',                         'ru': 'безнал',                             'zh': '非现金'},
    'plus_sign':            {'en': '+',                                'ru': '+',                                  'zh': '+'},
    'minus_sign':           {'en': '-',                                'ru': '-',                                  'zh': '-'},
    'back_arrow_raw':       {'en': '« Back',                           'ru': '« Назад',                            'zh': '« 返回'},

    'start_wait_approval': {
        'en': 'Please wait—your account has been sent to the administrator for approval.',
        'ru': 'Ожидайте — ваш аккаунт отправлен на рассмотрение администратору.',
        'zh': '请稍候——您的账号已发送给管理员审核。',
    },
    'start_success': {
        'en': 'Welcome back! Your emoji is already assigned.',
        'ru': 'Добро пожаловать! Эмодзи уже назначен.',
        'zh': '欢迎回来！您的表情已分配。',
    },


    # Генерация изображений
    'generate_no_text':     {'en': 'Specify text after /generate.',
                              'ru': 'Укажите текст после /generate.',
                              'zh': '在 /generate 之后指定文本。'},

    # Ошибки и уведомления
    'invalid_data_general': {'en': 'Invalid data.',                   'ru': 'Некорректные данные.',              'zh': '数据无效。'},
    'invalid_number':       {'en': 'Incorrect input, please try again.',
                              'ru': 'Некорректный ввод, попробуйте ещё раз.',
                              'zh': '输入有误，请重试。'},
    'no_photo_attached':    {'en': 'You did not attach a photo to the /id command.',
                              'ru': 'Вы не прикрепили фото к команде /id.',
                              'zh': '您未在 /id 命令中附加图片。'},
    'cancelled_simple':     {'en': 'Cancelled.',                       'ru': 'Отменено.',                           'zh': '已取消。'},

    # Place for any missing keys!
}

async def get_user_language(user_id: int) -> str:
    if not db.db_pool:
        return 'ru'
    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT language FROM user_settings WHERE user_id=$1", user_id
        )
    lang = row.get('language') if row else None
    return lang if lang in LANGUAGES else 'ru'

async def set_user_language(user_id: int, lang: str):
    if not db.db_pool or lang not in LANGUAGES:
        return
    async with db.db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_settings (user_id, language)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET language = EXCLUDED.language
            """,
            user_id, lang
        )

def get_message(lang: str, key: str, default: str = "", **kwargs) -> str:
    mapping = TRANSLATIONS.get(key)
    if mapping:
        text = mapping.get(lang) or mapping.get('ru') or mapping.get('en') or default
        return text.format(**kwargs)
    return default

@language_router.message(Command('lang'))
async def cmd_lang(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f'setlang_{code}')]
            for code, name in LANGUAGES.items()
        ]
    )
    await message.answer(get_message('ru', 'help_lang'), reply_markup=kb)

@language_router.callback_query(F.data.startswith('setlang_'))
async def callback_set_language(cb: CallbackQuery):
    _, lang_code = cb.data.split('_', 1)
    await set_user_language(cb.from_user.id, lang_code)
    await cb.answer(get_message(lang_code, 'lang_set_success', lang_name=LANGUAGES.get(lang_code)), show_alert=True)
