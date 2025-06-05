# handlers/taro_module.py

import os
import random
import openai
import logging
import html

from aiogram import Router, types
from aiogram.filters.command import Command
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)
router = Router()

# ────────────────────────────── Настройки ──────────────────────────────

# Папка с изображениями (JPEG-файлы должны лежать в handlers/TARO/)
TARO_FOLDER = os.path.join(os.path.dirname(__file__), "TARO")
REVERSED_CHANCE = 0.2

# ────────────────────────────── Колода карт ──────────────────────────────

# Старшие арканы
manara_cards = {
    "Шут.jpg": "Шут",
    "Маг.jpg": "Маг",
    "Верховная_жрица.jpg": "Верховная Жрица",
    "Императрица.jpg": "Императрица",
    "Император.jpg": "Император",
    "Жрец.jpg": "Жрец (Иерофант)",
    "Влюбленные.jpg": "Влюблённые",
    "Колесница.jpg": "Колесница",
    "Сила.jpg": "Сила",
    "Отшельник.jpg": "Отшельник",
    "Колесо_Фортуны.jpg": "Колесо Фортуны",
    "Правосудие.jpg": "Правосудие",
    "Наказание.jpg": "Наказание (Повешенный)",
    "Смерть.jpg": "Смерть",
    "Умеренность.jpg": "Умеренность",
    "Дьявол.jpg": "Дьявол",
    "Башня.jpg": "Башня",
    "Звезда.jpg": "Звезда",
    "Зеркало.jpg": "Зеркало (Луна)",
    "Солнце.jpg": "Солнце",
    "Суд.jpg": "Суд (Страшный Суд)",
    "Мир.jpg": "Мир"
}

# Младшие арканы: масти Воды, Воздуха, Земли, Огня
manara_cards.update({
    "Туз_воды.jpg": "Туз Воды",
    "2_воды.jpg": "Двойка Воды",
    "3_воды.jpg": "Тройка Воды",
    "4_воды.jpg": "Четвёрка Воды",
    "5_воды.jpg": "Пятёрка Воды",
    "6_воды.jpg": "Шестёрка Воды",
    "7_воды.jpg": "Семёрка Воды",
    "8_воды.jpg": "Восьмёрка Воды",
    "9_воды.jpg": "Девятка Воды",
    "10_воды.jpg": "Десятка Воды",
    "Слуга_воды.jpg": "Паж (Слуга) Воды",
    "Всадница_воды.jpg": "Всадница (Рыцарь) Воды",
    "Королева_воды.jpg": "Королева Воды",
    "Король_воды.jpg": "Король Воды"
})
manara_cards.update({
    "Туз_воздуха.jpg": "Туз Воздуха",
    "2_воздуха.jpg": "Двойка Воздуха",
    "3_воздуха.jpg": "Тройка Воздуха",
    "4_воздуха.jpg": "Четвёрка Воздуха",
    "5_воздуха.jpg": "Пятёрка Воздуха",
    "6_воздуха.jpg": "Шестёрка Воздуха",
    "7_воздуха.jpg": "Семёрка Воздуха",
    "8_воздуха.jpg": "Восьмёрка Воздуха",
    "9_воздуха.jpg": "Девятка Воздуха",
    "10_воздуха.jpg": "Десятка Воздуха",
    "Слуга_воздуха.jpg": "Паж (Слуга) Воздуха",
    "Всадница_воздуха.jpg": "Всадница (Рыцарь) Воздуха",
    "Королева_воздуха.jpg": "Королева Воздуха",
    "Король_воздуха.jpg": "Король Воздуха"
})
manara_cards.update({
    "Туз_земли.jpg": "Туз Земли",
    "2_земли.jpg": "Двойка Земли",
    "3_земли.jpg": "Тройка Земли",
    "4_земли.jpg": "Четвёрка Земли",
    "5_земли.jpg": "Пятёрка Земли",
    "6_земли.jpg": "Шестёрка Земли",
    "7_земли.jpg": "Семёрка Земли",
    "8_земли.jpg": "Восьмёрка Земли",
    "9_земли.jpg": "Девятка Земли",
    "10_земли.jpg": "Десятка Земли",
    "Слуга_земли.jpg": "Паж (Слуга) Земли",
    "Всадница_земли.jpg": "Всадница (Рыцарь) Земли",
    "Королева_земли.jpg": "Королева Земли",
    "Король_земли.jpg": "Король Земли"
})
manara_cards.update({
    "Туз_огня.jpg": "Туз Огня",
    "2_огня.jpg": "Двойка Огня",
    "3_огня.jpg": "Тройка Огня",
    "4_огня.jpg": "Четвёрка Огня",
    "5_огня.jpg": "Пятёрка Огня",
    "6_огня.jpg": "Шестёрка Огня",
    "7_огня.jpg": "Семёрка Огня",
    "8_огня.jpg": "Восьмёрка Огня",
    "9_огня.jpg": "Девятка Огня",
    "10_огня.jpg": "Десятка Огня",
    "Слуга_огня.jpg": "Паж (Слуга) Огня",
    "Всадница_огня.jpg": "Всадница (Рыцарь) Огня",
    "Королева_огня.jpg": "Королева Огня",
    "Король_огня.jpg": "Король Огня"
})


# ─────────────────────────── Вспомогательные функции ───────────────────────────

def draw_cards(cards_dict: dict, count: int = 3, reversed_chance: float = REVERSED_CHANCE):
    """
    Случайно выбираем `count` карт из словаря cards_dict.
    Возвращаем список кортежей (имя_файла, название_карты, is_reversed).
    """
    if count > len(cards_dict):
        raise ValueError("В колоде меньше карт, чем нужно вытащить.")
    filenames = random.sample(list(cards_dict.keys()), k=count)
    results = []
    for fname in filenames:
        card_name = cards_dict[fname]
        is_rev = (random.random() < reversed_chance)
        results.append((fname, card_name, is_rev))
    return results


def get_card_interpretation(card_name: str, position: str, is_reversed: bool) -> str:
    """
    Запрашивает ChatCompletion у OpenAI для интерпретации карты `card_name`.
    position — "Прошлое", "Настоящее" или "Будущее".
    is_reversed — перевёрнутая ли карта.
    """
    orientation_text = "перевёрнутая" if is_reversed else "прямая"
    prompt = (
        f"Ты — знаток Таро Манара. Я вытащил карту '{card_name}' в позиции '{position}'. "
        f"Она {orientation_text}. Объясни её значение в данном аспекте, "
        "учитывая особенности колоды Манара. Ответь дружелюбно и информативно."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # Или любой другой доступный моделью
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты выступаешь экспертом по Таро Манара. "
                        "Отвечай развёрнуто, дружелюбно и информативно, без излишнего мистицизма."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )
        answer_text = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI: {e}")
        answer_text = "Извините, произошла ошибка при получении интерпретации."

    return answer_text


# ─────────────────────────── Хендлер команды /tarot ───────────────────────────

@router.message(Command("taro"))
async def cmd_taro(message: types.Message):
    """
    Хендлер команды /taro:
    — вытягивает 3 карты и отправляет их в чат (с подписью);
    — после каждого рисунка отправляет текст интерпретации.
    """
    try:
        cards = draw_cards(manara_cards, count=3, reversed_chance=REVERSED_CHANCE)
    except ValueError as e:
        await message.answer(f"Ошибка: {e}")
        return

    positions = ["Прошлое", "Настоящее", "Будущее"]

    for i, (fname, card_name, is_rev) in enumerate(cards):
        pos_text = positions[i]
        orientation = " (перевёрнутая)" if is_rev else ""
        caption = f"{pos_text}: {card_name}{orientation}"
        full_path = os.path.join(TARO_FOLDER, fname)

        # Получаем текст интерпретации через OpenAI
        interpretation = get_card_interpretation(card_name, pos_text, is_rev)

        # Пробуем отправить фотографию карты
        try:
            photo = FSInputFile(full_path)
            await message.answer_photo(photo=photo, caption=caption)
        except FileNotFoundError:
            # Если файл не найден, отправляем подпись + текст интерпретации в Markdown
            await message.answer(
                f"**Не найден файл изображения**: {full_path}\n\n"
                f"{caption}\n\n{interpretation}",
                parse_mode="Markdown"
            )
            continue

        # Отправляем текст интерпретации (в HTML-виде)
        await message.answer(f"<pre>{html.escape(interpretation)}</pre>", parse_mode="HTML")
