# constants/booking_const.py

# Язык по умолчанию
LANG_DEFAULT = "ru"

# ID специальных пользователей и групп
SPECIAL_USER_ID           = 7935161063
FINANCIAL_REPORT_GROUP_ID = -1002374280400
BOOKING_REPORT_GROUP_ID   = -1002671780634

# Картинки для процесса бронирования
GROUP_CHOICE_IMG    = "photo/IMG_2585.JPG"
DAY_CHOICE_IMG      = "photo/IMG_2585.JPG"
TIME_CHOICE_IMG     = "photo/IMG_2585.JPG"
FINAL_BOOKED_IMG    = "photo/IMG_2585.JPG"

# Начисления спецпользователю
special_payments = {
    '0':  40,
    '1':  40,
    '2':  80,
    '3': 120,
}

# Отображение статуса эмодзи
status_mapping = {
    '0':  '✅',
    '1':  '✅2',
    '2': '✅✅',
    '3': '✅✅✅',
    '-1':'❌❌❌',
}

# Варианты распределения бонусов
distribution_variants = {
    'variant_100': {'0':100, '1':100, '2':200, '3':300},
    'variant_200': {'0':200, '1':200, '2':400, '3':600},
    'variant_300': {'0':300, '1':300, '2':600, '3':900},
    'variant_400': {'0':400, '1':400, '2':800, '3':1200},
}

# Начальные данные по группам
groups_data = {
    "Royal_1": {
        "chat_id": -1002503654146,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {
            "Сегодня": set(),
            "Завтра": set()
        },
        "booked_slots": {
            "Сегодня": [],
            "Завтра": []
        },
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_2": {
        "chat_id": -1002569987326,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {
            "Сегодня": set(),
            "Завтра": set()
        },
        "booked_slots": {
            "Сегодня": [],
            "Завтра": []
        },
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_3": {
        "chat_id": -1002699377044,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {
            "Сегодня": set(),
            "Завтра": set()
        },
        "booked_slots": {
            "Сегодня": [],
            "Завтра": []
        },
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_4": {
        "chat_id": -1002696765874,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {
            "Сегодня": set(),
            "Завтра": set()
        },
        "booked_slots": {
            "Сегодня": [],
            "Завтра": []
        },
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_5": {
        "chat_id": -1002555587028,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {
            "Сегодня": set(),
            "Завтра": set()
        },
        "booked_slots": {
            "Сегодня": [],
            "Завтра": []
        },
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    },
    "Royal_6": {
        "chat_id": -1002525751059,
        "salary_option": 1,
        "salary": 0,
        "cash": 0,
        "time_slot_statuses": {},
        "unavailable_slots": {
            "Сегодня": set(),
            "Завтра": set()
        },
        "booked_slots": {
            "Сегодня": [],
            "Завтра": []
        },
        "slot_bookers": {},
        "target_id": None,
        "distribution_variant": None,
        "message_id": None
    }
}
