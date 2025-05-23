# handlers/language.py

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
    # General messages
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
    'btn_cash':    {'en': 'Cash',          'ru': 'Наличные',     'zh': '现金'},
    'btn_beznal':  {'en': 'Cashless',      'ru': 'Безнал',       'zh': '非现金'},
    'btn_agent':   {'en': 'Agent',         'ru': 'Агент',        'zh': '代理'},
    'btn_back':    {'en': '« Back',        'ru': '« Назад',      'zh': '« 返回'},
    'btn_cancel':  {'en': '❌❌❌ Cancel',   'ru': '❌❌❌ Отменить', 'zh':'❌❌❌ 取消'},
    'btn_booking':        {'en': '⏰ Booking',       'ru': '⏰ Бронирование',      'zh': '⏰ 预订'},
    'btn_girls':          {'en': '💃 Girls',         'ru': '💃 Девушки',          'zh': '💃 女士'},
    'btn_schedule':       {'en': '📋 Schedule',      'ru': '📋 Расписание',       'zh': '📋 日程'},
    'btn_balance':        {'en': '🧮 Balance',       'ru': '🧮 Баланс',           'zh': '🧮 余额'},
    'btn_news':           {'en': '📰 News',          'ru': '📰 Новости',         'zh': '📰 新闻'},
    'btn_cancel_booking': {'en': '❌ Cancel booking','ru': '❌ Отмена брони',     'zh': '❌ 取消预订'},

    # Menu headers/errors
    'news_header':   {
        'en': 'Latest news:',
        'ru': 'Последние новости:',
        'zh': '最新新闻：',
    },
    'menu_unknown':  {
        'en': 'Unknown menu action!',
        'ru': 'Неизвестная команда меню!',
        'zh': '未知的菜单操作！',
    },
}


async def get_user_language(user_id: int) -> str:
    """
    Retrieve the user's language from DB or default to Russian ('ru').
    """
    if not db.db_pool:
        return 'ru'
    async with db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT language FROM user_settings WHERE user_id=$1", user_id
        )
    lang = row.get('language') if row else None
    return lang if lang in LANGUAGES else 'ru'

async def set_user_language(user_id: int, lang: str):
    """
    Save or update the user's language preference in DB.
    """
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
    """
    Return the translated message by key and language, formatting with kwargs.
    """
    mapping = TRANSLATIONS.get(key, {})
    text = mapping.get(lang) or mapping.get('ru') or ''
    return text.format(**kwargs)

@language_router.message(Command('lang'))
async def cmd_lang(message: Message):
    """
    Command handler to choose language.
    """
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f'setlang_{code}')]
            for code, name in LANGUAGES.items()
        ]
    )
    # Use default 'ru' for prompt
    await message.answer(get_message('ru', 'help_lang'), reply_markup=kb)

@language_router.callback_query(F.data.startswith('setlang_'))
async def callback_set_language(cb: CallbackQuery):
    """
    Callback handler for setting language.
    """
    _, lang_code = cb.data.split('_', 1)
    await set_user_language(cb.from_user.id, lang_code)
    await cb.answer(f"Language set to {LANGUAGES.get(lang_code)}", show_alert=True)
