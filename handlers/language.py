from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import db

language_router = Router()

# Supported languages
LANGUAGES = {
    'en': 'English',
    'ru': 'Русский',
    'zh': '中文',
}

# Translation dictionary
TRANSLATIONS = {
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
        'en': 'No such booking found.',
        'ru': 'Не найдена такая бронь!',
        'zh': '未找到该预订。',
    },
    'no_permission': {
        'en': 'You do not have permission to perform this action.',
        'ru': 'У вас нет прав для выполнения этого действия.',
        'zh': '您没有权限执行此操作。',
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
    'distribution_message': {
        'en': 'Credited {amount}, balance {balance}',
        'ru': 'Начислено {amount}, баланс {balance}',
        'zh': '已到账{amount}，余额{balance}',
    },

    # Booking flow
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

    # Payment flow
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

    # Language command
    'help_lang': {
        'en': 'Select your language',
        'ru': 'Выберите язык',
        'zh': '选择语言',
    },

    # Button labels
    'btn_cash':           {'en': 'Cash',            'ru': 'Наличные',      'zh': '现金'},
    'btn_beznal':         {'en': 'Cashless',        'ru': 'Безнал',        'zh': '非现金'},
    'btn_agent':          {'en': 'Agent',           'ru': 'Агент',         'zh': '代理'},
    'btn_back':           {'en': '« Back',          'ru': '« Назад',       'zh': '« 返回'},
    'btn_cancel':         {'en': '❌❌❌ Cancel',     'ru': '❌❌❌ Отменить', 'zh': '❌❌❌ 取消'},
    'btn_booking':        {'en': '⏰ Booking',       'ru': '⏰ Бронирование','zh': '⏰ 预订'},
    'btn_girls':          {'en': '💃 Girls',         'ru': '💃 Девушки',     'zh': '💃 女士'},
    'btn_schedule':       {'en': '📋 Schedule',      'ru': '📋 Расписание',  'zh': '📋 日程'},
    'btn_balance':        {'en': '🧮 Balance',       'ru': '🧮 Баланс',      'zh': '🧮 余额'},
    'btn_news':           {'en': '📰 News',          'ru': '📰 Новости',    'zh': '📰 新闻'},
    'btn_cancel_booking': {'en': '❌ Cancel booking','ru': '❌ Отмена брони', 'zh': '❌ 取消预订'},

    # Menu headers/errors
    'news_header':        {'en': 'Latest news:',      'ru': 'Последние новости:', 'zh': '最新新闻：'},
    'menu_unknown':       {'en': 'Unknown menu action!','ru': 'Неизвестная команда меню!','zh': '未知的菜单操作！'},

    # Cleanup (/clean)
    'clean_time': {
        'en': 'Time',
        'ru': 'Время',
        'zh': '时间',
    },
    'clean_salary': {
        'en': 'Salary',
        'ru': 'Зарплата',
        'zh': '工资',
    },
    'clean_cash': {
        'en': 'Cash',
        'ru': 'Наличные',
        'zh': '现金',
    },
    'clean_all': {
        'en': 'Clear all data',
        'ru': 'Стереть все данные',
        'zh': '清除所有数据',
    },
    'clean_prompt': {
        'en': 'What would you like to clear?',
        'ru': 'Что вы хотите стереть?',
        'zh': '您想清除什么？',
    },
    'clean_confirm_all': {
        'en': 'Yes, clear all',
        'ru': 'Да, стереть все данные',
        'zh': '是的，全部清除',
    },
    'clean_confirm_all_prompt': {
        'en': 'Confirm clearing ALL data (time/salary/cash) for ALL groups?',
        'ru': 'Подтвердите удаление ВСЕХ данных (время/зарплата/наличные) по ВСЕМ группам?',
        'zh': '确认清除所有群组的所有数据（时间/工资/现金）？',
    },
    'clean_section_prompt': {
        'en': 'You chose: {section}\nSelect a group or "Clear all {section}"',
        'ru': 'Вы выбрали: {section}\nВыберите группу или «Стереть все {section}»',
        'zh': '您已选择：{section}\n请选择一个群组或“清除所有{section}”',
    },
    'clean_confirm_section_prompt': {
        'en': 'Confirm clearing {section} for ALL groups?',
        'ru': 'Подтвердите удаление {section} по ВСЕМ группам?',
        'zh': '确认清除所有群组的{section}？',
    },
    'clean_confirm_group': {
        'en': 'Yes, clear',
        'ru': 'Да, стереть!',
        'zh': '是的，清除！',
    },
    'clean_group_prompt': {
        'en': 'Confirm clearing {section} for group {group}',
        'ru': 'Подтвердите удаление {section} для группы {group}',
        'zh': '确认清除群组{group}的{section}？',
    },
    'clean_done_all': {
        'en': 'Cleared all {section} for all groups.',
        'ru': 'Все данные «{section}» стёрты для всех групп.',
        'zh': '已为所有群组清除所有{section}。',
    },
    'clean_done_group': {
        'en': 'Cleared {section} for group {group}.',
        'ru': 'Данные «{section}» стёрты для группы {group}.',
        'zh': '已为群组{group}清除{section}。',
    },
    'cancelled': {
        'en': 'Cancelled.',
        'ru': 'Отменено.',
        'zh': '已取消。',
    },

    # News management
    'btn_add': {
        'en': 'Add',
        'ru': 'Добавить',
        'zh': '添加',
    },
    'btn_edit': {
        'en': 'Edit',
        'ru': 'Редактировать',
        'zh': '编辑',
    },
    'btn_delete': {
        'en': 'Delete',
        'ru': 'Удалить',
        'zh': '删除',
    },
    'news_manage': {
        'en': 'Manage news:',
        'ru': 'Управление новостями:',
        'zh': '管理新闻：',
    },
    'cancelled': {
        'en': 'Cancelled.',
        'ru': 'Отменено.',
        'zh': '已取消。',
    },
    'news_deleted_all': {
        'en': 'All news deleted.',
        'ru': 'Все новости удалены.',
        'zh': '所有新闻已删除。',
    },
    'done': {
        'en': 'Done.',
        'ru': 'Готово.',
        'zh': '完成。',
    },
    'news_edit_prompt': {
        'en': 'Editing (demo). Send new text to update record id=1.',
        'ru': 'Редактирование (демо). Пришлите новый текст — обновим запись c id=1.',
        'zh': '编辑（演示）。发送新文本以更新 id=1。',
    },
    'news_photos_prompt': {
        'en': 'Send up to 10 photos. Then — /done',
        'ru': 'Отправьте до 10 фотографий. После — /done',
        'zh': '最多发送10张照片。然后 — /done',
    },
    'news_photo_limit': {
        'en': 'Limit is 10 photos! Send /done to finish.',
        'ru': 'Лимит 10 фото! Введите /done, чтобы завершить.',
        'zh': '最多10张照片限制！发送 /done 完成。',
    },
    'news_photo_received': {
        'en': 'Photo received. Send more or /done',
        'ru': 'Фото получено. Отправьте ещё или /done',
        'zh': '已收到照片。发送更多或 /done',
    },
    'news_no_photos': {
        'en': 'No photos. /done cancelled.',
        'ru': 'Нет фото. /done отменено.',
        'zh': '没有照片。/done 已取消。',
    },
    'news_photos_saved': {
        'en': 'Photos saved. Now send news text:',
        'ru': 'Фотографии сохранены. Теперь отправьте текст новости:',
        'zh': '照片已保存。现在发送新闻文本：',
    },
    'news_saved': {
        'en': 'News saved successfully!',
        'ru': 'Новости успешно сохранены!',
        'zh': '新闻已成功保存！',
    },
    'news_updated': {
        'en': 'News (id=1) updated!',
        'ru': 'Новость (id=1) обновлена!',
        'zh': '新闻 (id=1) 已更新！',
    },
    'db_not_initialized': {
        'en': 'db_pool == None, not initialized!',
        'ru': 'db_pool == None, не инициализирован!',
        'zh': 'db_pool == None，未初始化！',
    },
    'news_none': {
        'en': 'No news yet.',
        'ru': 'Пока нет новостей.',
        'zh': '暂时没有新闻。',
    },
    'news_no_text': {
        'en': '(no text)',
        'ru': '(без текста)',
        'zh': '(无文本)',
    },
    'news_item': {
        'en': '📰 ID={id}: {text}',
        'ru': '📰 ID={id}: {text}',
        'zh': '📰 ID={id}：{text}',
    },
    'news_photo': {
        'en': 'Photo',
        'ru': 'Фото',
        'zh': '照片',
    },
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

def get_message(lang: str, key: str, **kwargs) -> str:
    mapping = TRANSLATIONS.get(key, {})
    text = mapping.get(lang) or mapping.get('ru') or ''
    return text.format(**kwargs)

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
    await cb.answer(f"Language set to {LANGUAGES.get(lang_code)}", show_alert=True)
