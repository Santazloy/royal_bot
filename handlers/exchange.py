# handlers/exchange.py

import logging
import requests
import os

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from handlers.language import get_user_language, get_message
from utils.bot_utils import safe_answer
from utils.text_utils import format_html_pre  # используем готовую обёртку

logger = logging.getLogger(__name__)
router = Router()

# Константы валют и их флаги/имена
CURRENCIES = {
    'RUB': {'name': 'Рубль',  'flag': '🇷🇺'},
    'USD': {'name': 'Доллар', 'flag': '🇺🇸'},
    'UAH': {'name': 'Гривна', 'flag': '🇺🇦'},
    'CNY': {'name': 'Юань',   'flag': '🇨🇳'},
    'EUR': {'name': 'Евро',   'flag': '🇪🇺'},
    'USDT': {'name': 'Tether','flag': '🏴‍☠️'},
}


def get_usdt_rate_coingecko():
    """
    Запрашивает курс USDT через CoinGecko API (в USD) и возвращает обратное значение.
    """
    url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            logger.info("CoinGecko response for USDT: %s", data)
            usd_value = data.get("tether", {}).get("usd")
            if usd_value and usd_value != 0:
                return 1.0 / float(usd_value)
    except Exception as e:
        logger.error("Ошибка при получении курса USDT с CoinGecko: %s", e)
    return None


def get_fiat_rates():
    """
    Запрашивает базовые курсы (USD → RUB, UAH, CNY, EUR) через open.er-api.com.
    """
    url = "https://open.er-api.com/v6/latest/USD"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            logger.info("open.er-api.com response: %s", data)
            rates = data.get("rates", {})
            filtered = {
                key: rates.get(key)
                for key in ["RUB", "UAH", "CNY", "EUR"]
            }
            filtered["USD"] = 1.0
            logger.info("Фиатные курсы: %s", filtered)
            return filtered
    except Exception as e:
        logger.error("Ошибка при получении курсов с open.er-api.com: %s", e)
    return {}


def get_all_rates(base_currency: str):
    """
    Возвращает словарь всех курсов относительно base_currency.
    Сначала запрашивает фиатные курсы, затем добавляет USDT.
    """
    rates = get_fiat_rates()
    usdt_rate = get_usdt_rate_coingecko()
    if usdt_rate is not None:
        rates["USDT"] = usdt_rate
    if not rates:
        return {}

    base_currency = base_currency.upper()
    # Если базовая валюта — USD, возвращаем «как есть»
    if base_currency == "USD":
        return rates

    if base_currency in rates:
        base_to_usd = 1.0 / rates[base_currency]
        converted = {}
        for code, r in rates.items():
            converted[code] = base_to_usd * r
        return converted

    return {}


def convert_and_format(amount: float, base_currency: str) -> str:
    """
    Конвертирует amount из base_currency во все доступные валюты
    и возвращает строку с HTML-разметкой, обёрнутую в <pre>…</pre>.
    """
    base_currency = base_currency.upper()
    rates = get_all_rates(base_currency)
    if not rates:
        return format_html_pre("❌ Не удалось получить курсы валют.")

    result_lines = [f"💱 {amount} {base_currency} ="]
    for code, rate in rates.items():
        if code == base_currency:
            continue
        converted = round(amount * rate, 2)
        flag = CURRENCIES.get(code, {}).get("flag", "")
        name = CURRENCIES.get(code, {}).get("name", code)
        result_lines.append(f"{flag} {converted} {code} — {name}")

    # Собираем многострочный текст и оборачиваем в <pre>
    full_text = "\n".join(result_lines)
    return format_html_pre(full_text)


# FSM для состояния ожидания ввода
class ConversionStates(StatesGroup):
    waiting_for_input = State()


@router.callback_query(F.data == "conversion")
async def callback_conversion(callback: CallbackQuery, state: FSMContext):
    """
    При нажатии кнопки “Конвертация”:
    1) удаляем старое сообщение бота (админ-меню),
    2) отправляем фото + инструкцию (без <pre>),
    3) переводим FSM в состояние ожидания ввода суммы и кода валюты.
    """
    # Удаляем предыдущее сообщение бота (меню)
    try:
        await callback.message.delete()
    except:
        pass

    lang = await get_user_language(callback.from_user.id)
    prompt = get_message(
        lang,
        "enter_conversion",
        default="Введите сумму и код валюты (например: 100 USD)"
    )

    # Убедимся, что файл существует; иначе можем указать полный путь
    photo_path = "photo/IMG_2585.JPG"
    if not os.path.exists(photo_path):
        # предполагаем, что текущая рабочая директория — корень проекта
        # проверьте фактическое расположение картинки и при необходимости уточните путь
        logger.warning("Photo for conversion prompt not found: %s", photo_path)

    # Отправляем фото и инструкцию (без parse_mode, так как здесь чистый текст)
    await safe_answer(
        callback,
        photo=photo_path,
        caption=prompt
    )
    await state.set_state(ConversionStates.waiting_for_input)


@router.message(ConversionStates.waiting_for_input, F.text)
async def process_conversion_input(message: Message, state: FSMContext):
    """
    Обрабатывает текст вида “100 USD”:
    1) проверяет формат,
    2) конвертирует и форматирует результат (с <pre>),
    3) удаляет инструкцию и отправляет фото + результат,
    4) сбрасывает FSM.
    """
    text = message.text.strip()
    parts = text.split()
    if len(parts) != 2:
        error = format_html_pre("❌ Неверный формат. Введите, например: 100 USD")
        return await safe_answer(message, error, parse_mode=ParseMode.HTML)

    amount_str, base_currency = parts
    try:
        amount = float(amount_str.replace(",", "."))
    except ValueError:
        error = format_html_pre("❌ Неверная сумма. Попробуйте ещё раз.")
        return await safe_answer(message, error, parse_mode=ParseMode.HTML)

    # Получаем результат конвертации (уже обёрнутый в <pre>…</pre>)
    result = convert_and_format(amount, base_currency)

    # Путь до той же картинки
    photo_path = "photo/IMG_2585.JPG"
    if not os.path.exists(photo_path):
        logger.warning("Photo for conversion result not found: %s", photo_path)

    # Отправляем фото + результат (parse_mode=HTML, чтобы <pre> работал)
    await safe_answer(
        message,
        photo=photo_path,
        caption=result,
        parse_mode=ParseMode.HTML
    )

    # Сброс FSM
    await state.clear()
