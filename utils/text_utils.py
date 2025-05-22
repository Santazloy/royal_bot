# utils/text_utils.py

import html
from constants.booking_const import LANG_DEFAULT

def get_message(lang: str, key: str, **kwargs) -> str:
    translations = {
        "ru": {
            "no_action":           "Просто заглушка-кнопка без действия.",
            "invalid_data":        "Некорректные данные!",
            "no_such_group":       "Нет такой группы!",
            "no_such_booking":     "Не найдена такая бронь!",
            "no_permission":       "У вас нет прав!",
            "incorrect_input":     "Неверный ввод числа!",
            "changed_balance_user":"Баланс пользователя {op}{amount} => {balance}",
            "distribution_message":"Начислено {amount}, баланс {balance}",
            "enter_payment_amount":"Введите сумму (числом):",
            "select_method_payment":"Выберите способ оплаты:",
            "slot_booked":         "Слот {time} ({day}) в группе {group} забронирован!",
            "today":               "Сегодня",
            "tomorrow":            "Завтра",
            "choose_time_styled":  "Выберите свободное время на {day}:",
            "all_bookings_title":  "Все брони за {day}",
            "no_active_bookings":  "Активных бронирований нет.",
            "no_bookings":         "Нет бронирований.",
        }
    }
    tmpl = translations.get(lang, translations[LANG_DEFAULT]).get(key, key)
    return tmpl.format(**kwargs)

def format_html_pre(text: str) -> str:
    """Оборачивает в <pre> с экранированием HTML."""
    return f"<pre>{html.escape(text)}</pre>"