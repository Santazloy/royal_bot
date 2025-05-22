import os
import asyncio
import logging
import random
import subprocess
import requests
import openai

from aiogram import Bot, Router, types
from aiogram.enums import ChatAction
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter, CommandStart
from aiogram import F

from config import FFMPEG_CMD, OPENAI_API_KEY
from handlers.booking import cmd_book

logger = logging.getLogger(__name__)

# Єдині ключові слова для прайсу
PRICE_KEYWORDS = ["прайс", "вартість"]

# ---------------------- Полный прайс, разбитый на 4 части ---------------
PRICE_PART_1 = """КОСМЕТОЛОГІЧНІ ПРОЦЕДУРИ

Консультація на апараті Observ 520 — 1500 грн
Консультація anti-age — 1000 грн
Консультація акне/проблемна шкіра — 1000 грн
Підбір домашнього догляду/процедур — 800 грн

ЧИСТКА ОБЛИЧЧЯ / СПИНИ

Комбінована чистка обличчя — 1600 грн
Ультразвукова чистка обличчя — 1200 грн
Механічна чистка обличчя — 1400 грн
Чистка обличчя на косметиці HydroPeptide — 1800 грн
Чистка обличчя з ензимним пілінгом — 1800 грн
Чистка спини — 1800 грн

ПІЛІНГ

Серединний пілінг TCA — 2000 грн
Серединний пілінг PRX-T33 — 2000 грн
BioRePeelCl3 — 1800 грн
Пілінг Medik8 Even — 1000 грн
Пілінг Medik8 Clarity — 1000 грн
Retibooster — 3300 грн
Peptyglow — 1400 грн
Jalupro Glow PEEL — 1800 грн

ДОГЛЯД IMAGE

Пілінг Perfect Lift Solution — 1200 грн
Ензимний пілінг Ormedik — 1200 грн
Карбокситерапія — насичення шкіри киснем — 1200 грн
Антиоксидантний догляд з вітаміном C — 1200 грн
Ліфтинговий пілінг Signature — 1200 грн

ДОГЛЯД CASMARA

Goji (антиоксидант, профілактика старіння) — 1600 грн
Q10 Rescue (інтенсивне живлення) — 1600 грн
Ocean Miracle (антивіковий та зміцнюючий) — 1600 грн
Skin Sensation (відновлюючий, зволожуючий, ліфтинговий) — 1600 грн

ДОГЛЯД HYDROPEPTIDE

Висвітлюючий догляд з вітаміном C — 1400 грн
Чорничний лимонад з вітаміном C — 1400 грн
Чорничний пілінг для чутливої шкіри — 1400 грн
Антивіковий пілінг зі стовбуровими клітинами — 1400 грн
Гарбузовий пілінг для глибокого очищення — 1400 грн
Стоп акне — 1400 грн
Вогонь і лід — 1400 грн

ДОГЛЯД IS CLINICAL

Вогонь і лід — 2200 грн
Пінний ферментативний догляд — 1800 грн

ДОГЛЯД MEDIK8

Заспокійливий догляд — 1200 грн
Очищаючий догляд — 1200 грн

ФОТОТЕРАПІЯ IPL

Все обличчя — 2800 грн
Щоки + ніс + підборіддя — 2400 грн
Лоб — 1300 грн
Щоки + ніс — 2000 грн
Щоки + підборіддя — 1800 грн
Щоки — 1600 грн
Ніс — 1300 грн
Підборіддя — 1300 грн
Обличчя + шия + декольте — 4000 грн
Обличчя + шия — 3500 грн
Шия — 1500 грн
Декольте — 2800 грн
Кисті рук — 2200 грн
Спина — 3500 грн
"""

PRICE_PART_2 = """АПАРАТНІ ПРОЦЕДУРИ

Мікроструми — 1200 грн
УЗ-фонофорез — 1200 грн
Мікродермабразія — 1200 грн

AQUAPURE

Гідропілінг Aquapure — 2500 грн

RF-ЛІФТИНГ ENDYMED 3DEEP (МІКРОГОЛКОВИЙ)

1000 імпульсів — 11000 грн
Обличчя — 9000 грн
Обличчя + шия + декольте — 11000 грн

RF-ЛІФТИНГ ENDYMED 3DEEP (НЕІНВАЗИВНИЙ)

Зона навколо очей — 1500 грн
Зона навколо губ — 1100 грн
Щоки — 1200 грн
Підборіддя — 1200 грн
Ноги (внутрішня частина стегна) — 700 грн
Ноги (зовнішня частина стегна) — 700 грн
Ноги (ділянка під сідницею) — 700 грн
Сідниці — 700 грн
Внутрішня частина стегна + ділянка під сідницею + сідниці — 1800 грн
Живіт — 700 грн
Живіт + боки — 1000 грн
Коліна — 400 грн

*при оплаті 6-ти процедур будь-яких 2-ох зон — знижка 10%
*при оплаті 6-ти процедур будь-яких 3-ох зон — знижка 15%

ЛАЗЕРНА ЕПІЛЯЦІЯ (LUMENIS)

Верхня губа — 300 грн
Підборіддя — 300 грн
Міжбрів’я — 200 грн
Лінія чола — 350 грн
Все обличчя — 1100 грн
Пахові області — 500 грн
Руки до ліктя — 700 грн
Руки повністю — 1000 грн
Гомілки — 1300 грн
Стегна — 1200 грн
Коліна — 300 грн
Сідниці — 700 грн
Ноги повністю — 2350 грн
Глибоке бікіні — 1200 грн
Бікіні по лінії трусиків — 800 грн
Груди — 600 грн
Ореоли — 300 грн
Біла лінія живота — 350 грн
Спина — 1800 грн

КОМПЛЕКС 1 (ноги + пахи + бікіні глибоке) — 3000 грн
КОМПЛЕКС 2 (ноги до колін + глибоке бікіні + пахи) — 2200 грн
КОМПЛЕКС 3 (глибоке бікіні + пахи) — 1400 грн
"""

PRICE_PART_3 = """ІН’ЄКЦІЙНІ ПРОЦЕДУРИ

КОНТУРНА ПЛАСТИКА ГУБ
Teosyal RHA 1 (1.0) — 190€
Teosyal RHA 2 (1.0) — 190€
Teosyal RHA 3 (1.0) — 190€
Teosyal RHA Kiss (0.7) — 160€
Restylane Kiss (1.0) — 190€
Розчинення губ — 2000 грн

КОНТУРНА ПЛАСТИКА
Teosyal Ultra Deep — 220€
Teosyal RHA 4 — 220€
Restylane Volyme — 220€
Restylane Defyne — 220€
Restylane Lyft — 220€

КОЛАГЕНОСТИМУЛЯЦІЯ
Gouri — 180€
Karisma — 190€
Гідроксиапатит Ca Radiesse — 250€
Feijia для ділянки навколо очей — 6000 грн

БОТУЛІНОТЕРАПІЯ NEURONOX/BOTOX
Full face — 12500 / 14000 грн
Міжбрів’я — 2600 / 3300 грн
Лоб — 2600 / 3300 грн
Очі — 2600 / 3300 грн
Верхня третина — 7500 / 9500 грн
Платизма — 5000 / 6500 грн
Корекція надмірного потовиділення — 11000 / 13500 грн
Ясенна посмішка — 1500 грн
Корекція підборіддя — 1500 грн
Корекція жувальних м’язів — 4500 / 6000 грн
Dao — 1500 грн

БІОРЕВІТАЛІЗАЦІЯ
Jalupro — 3800 грн
Jalupro HMW — 5600 грн
Jalupro eye — 4600 грн
Jalupro Super Hydro — 7300 грн
Teosyal Redensity 1 (1 мл) — 3800 грн
Teosyal Redensity 1 (3 мл) — 8500 грн

МЕЗОТЕРАПІЯ
Rejuran S — 4300 грн
Rejuran HB — 5200 грн
Rejuran i — 4300 грн
Rejuran Healer (2 мл) — 7500 грн
Полінуклеотиди Plinest Mastelli (3.0) — 4800 грн
Plenhyage strong — 9700 грн
Мезококтейль AKN-ID акне — 1600 грн
Pluryal Mesoline Hair (волосся) — 1250 грн
Plinest Hair Mastelli (волосся) — 4800 грн
Ліполітики (10.0) — 1700 грн
"""

PRICE_PART_4 = """МАСАЖ

ВАКУУМНО-ЛІМФОДРЕНАЖНИЙ SPM
Обличчя — 1200 грн
Ноги + сідниці — 1000 грн
Ноги + сідниці + живіт — 1200 грн
Ноги + сідниці + живіт + спина — 1500 грн
Ноги + сідниці + живіт + спина + руки — 1800 грн

ЕНДОСФЕРА

45 хв (ноги + живіт + сідниці) — 1500 грн
60 хв (ноги + живіт + сідниці + спина) — 1800 грн
75 хв (ноги + живіт + сідниці + спина + руки) — 2100 грн
Обличчя — 1400 грн

*при оплаті 6-ти процедур (ноги + живіт + сідниці) вартість 8100 грн
*при оплаті 6-ти процедур (ноги + живіт + сідниці + спина) — 9700 грн
*при оплаті 6-ти процедур (ноги + живіт + сідниці + спина + руки) — 11000 грн

*при оплаті 10-ти процедур (ноги + живіт + сідниці) — 12000 грн
*при оплаті 10-ти процедур (ноги + живіт + сідниці + спина) — 15000 грн
*при оплаті 10-ти процедур (ноги + живіт + сідниці + спина + руки) — 18000 грн
"""

# Собираем наши блоки в список, чтобы удобно отправлять
price_blocks = [PRICE_PART_1, PRICE_PART_2, PRICE_PART_3, PRICE_PART_4]

SYSTEM_PROMPT_UA = (
    "Ти — Оксана, адміністратор косметологічного центру «Ботокс Спайс» у Львові. "
    "Ти чудово знаєш все про косметологію, ін'єкції, догляд за шкірою, епіляцію, масаж тощо. "
    "У твоєму центрі є розширений прайс із багатьох процедур. "
    "Відповідай виключно українською мовою, в дружньому та професійному тоні, "
    "надавай поради клієнтам, розповідай про різницю між процедурами і підкреслюй їхні переваги. "
    "Якщо запитують про ціни – можеш сказати, що є розподіл на 4 великих блоки (косметологія, апаратні процедури, ін’єкції, масаж). "
    "Також якщо хтось питає про власника чи відкриття центру – кажи, що директор Тетяна дуже талановита людина, сама створила цей бізнес у Львові. "
    "Якщо хтось попросить розповісти про Тетяну ти розказуєш дивовижну історію з пригодами. "
    "Додавай трохи медичної термінології у відповіді про косметологію. "
    "Прошу всі відповіді обгортати в тег <pre>...</pre>, дякую!"
)

def build_final_answer(gpt_text: str, voice_mode: bool = False) -> str:
    """
    Обгортає gpt_text у <pre> (для тексту), додає телефон.
    """
    appended_line_text  = "Запрошую Вас зв’язатися з нами для запису на прийом, телефон: 0687075187."
    appended_line_voice = "Запрошую Вас зв’язатися з нами для запису на прийом, телефон 0687075187."

    if voice_mode:
        # Голосова відповідь — не додаємо <pre>
        return f"{gpt_text}\n\n{appended_line_voice}"
    else:
        # Текстова відповідь
        return f"<pre>{gpt_text}\n\n{appended_line_text}</pre>"

async def generate_gpt_reply_ua(user_text: str) -> str:
    openai.api_key = OPENAI_API_KEY
    try:
        resp = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model="gpt-4o",  # або 'gpt-3.5-turbo'
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_UA},
                    {"role": "user",   "content": user_text}
                ],
                temperature=0.7
            )
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"GPT error: {e}")
        return "Вибачте, GPT недоступний у цей момент."

async def send_voice_reply_ua(message: types.Message, text_for_voice: str):
    """
    Генерує голосове повідомлення, якщо вказано налаштування TTS.
    text_for_voice тут без <pre> -
    """
    TTS_API_KEY       = os.getenv("TTS_API_KEY", "")
    TTS_API_ENDPOINT  = os.getenv("TTS_API_ENDPOINT", "")
    ffmpeg_executable = FFMPEG_CMD or "ffmpeg"

    if not TTS_API_KEY or not TTS_API_ENDPOINT:
        await message.answer(f"<pre>{text_for_voice}</pre>", parse_mode="HTML")
        return

    try:
        payload = {
            "input": text_for_voice,
            "voice": "coral",
            "response_format": "opus",
            "model": "tts-1-hd"
        }
        headers = {
            "Authorization": f"Bearer {TTS_API_KEY}",
            "Content-Type": "application/json"
        }
        resp = requests.post(TTS_API_ENDPOINT, json=payload, headers=headers)
        if resp.status_code == 200:
            with open("raw.opus", "wb") as f:
                f.write(resp.content)

            subprocess.run([
                ffmpeg_executable, "-y",
                "-i", "raw.opus",
                "-c:a", "libopus",
                "-ar", "48000",
                "-ac", "1",
                "-b:a", "64k",
                "-map_metadata", "-1",
                "-f", "ogg", "speech.ogg"
            ], check=True)

            await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)
            voice_file = FSInputFile("speech.ogg")
            await message.answer_voice(voice_file)
        else:
            await message.answer(
                f"Помилка TTS ({resp.status_code}): {resp.text}\n<pre>{text_for_voice}</pre>",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"TTS error: {e}")
        await message.answer(f"Помилка TTS: {e}\n<pre>{text_for_voice}</pre>", parse_mode="HTML")

# ------------------- WHISPER Розпізнавання --------------------------------
async def transcribe_with_whisper_openai(filename: str) -> str:
    """
    Використовує OpenAI Whisper API для розпізнавання.
    Припускаємо, що у вас є openai.Audio.transcribe(...) в бета-доступі.
    """
    openai.api_key = OPENAI_API_KEY
    with open(filename, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return transcript["text"]

# ------------------- Основний router --------------------------------------
mamasan_router = Router()

@mamasan_router.message(F.voice)
async def handle_voice_message(message: types.Message, state: FSMContext):
    """
    Обробка голосового повідомлення:
      1. Завантажуємо файл
      2. Розпізнаємо Whisper-ом
      3. Передаємо у GPT
      4. Відповідаємо голосом (бо це voice)
    """
    # 1) Отримуємо посилання на файл
    voice_file_id = message.voice.file_id
    file_info = await message.bot.get_file(voice_file_id)
    file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_info.file_path}"

    filename = "temp_voice.ogg"
    resp = requests.get(file_url)
    with open(filename, "wb") as f:
        f.write(resp.content)

    # 2) Розпізнаємо текст
    text = await transcribe_with_whisper_openai(filename)
    text = text.strip()
    if not text:
        await message.answer("<pre>Не вдалося розпізнати голосове повідомлення :(</pre>", parse_mode="HTML")
        return

    # 3) Якщо це слово "прайс" чи "вартість" -> відправляємо всі блоки і завершуємо
    txt_lower = text.lower()
    if any(k in txt_lower for k in PRICE_KEYWORDS):
        for block in price_blocks:
            await message.answer(f"<pre>{block}</pre>", parse_mode="HTML")
        return

    # 4) Генеруємо GPT відповідь
    gpt_core_reply = await generate_gpt_reply_ua(text)

    # 5) Формуємо фінальну стрічку (voice_mode=True)
    final_str = build_final_answer(gpt_core_reply, voice_mode=True)

    # 6) Відправляємо голосом
    await send_voice_reply_ua(message, final_str)

    # 7) Перевірка на бронювання
    booking_keywords_ua = ["забронювати", "записатися", "бронювання"]
    if any(bk in txt_lower for bk in booking_keywords_ua):
        await message.answer("<pre>Зараз допоможу з бронюванням! Запускаю вибір групи…</pre>", parse_mode="HTML")
        await cmd_book(message, state)

@mamasan_router.message()
async def handle_text_message(message: types.Message, state: FSMContext):
    """
    Якщо звичайне текстове повідомлення:
    - якщо "прайс"/"вартість" -> 4 блоки
    - інакше GPT-відповідь (текстова)
    - якщо текст містить слова про бронювання -> cmd_book
    """
    if not message.text:
        return

    txt_lower = message.text.lower()

    # Перевірка "прайс" або "вартість"
    if any(k in txt_lower for k in PRICE_KEYWORDS):
        for block in price_blocks:
            await message.answer(f"<pre>{block}</pre>", parse_mode="HTML")
        return

    # Генеруємо GPT
    gpt_core_reply = await generate_gpt_reply_ua(message.text)
    final_str = build_final_answer(gpt_core_reply, voice_mode=False)
    await message.answer(final_str, parse_mode="HTML")

    # Якщо "забронювати"/"записатися"/"бронювання"
    booking_keywords_ua = ["забронювати", "записатися", "бронювання"]
    if any(bk in txt_lower for bk in booking_keywords_ua):
        await message.answer("<pre>Зараз допоможу з бронюванням! Запускаю вибір групи…</pre>", parse_mode="HTML")
        await cmd_book(message, state)