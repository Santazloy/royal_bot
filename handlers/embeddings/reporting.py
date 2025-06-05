# handlers/embedding/reporting.py

import textwrap
import logging
from datetime import datetime, timedelta
from aiogram import Bot

from config import VECTOR_GROUP_IDS
from handlers.embedding.openai_utils import generate_analysis_text
from db import get_messages_for_period  # должно быть в вашем db.py

logger = logging.getLogger(__name__)


async def send_report_for_period(bot: Bot, group_id: int, days: int = 1):
    """
    Формирует и отправляет отчёт по переписке за последние `days` дней.
    """
    now_utc = datetime.utcnow()
    start_utc = now_utc - timedelta(days=days)

    # 1) Забираем сообщения из БД
    messages = await get_messages_for_period(group_id, start_utc, now_utc)
    if not messages:
        await bot.send_message(
            group_id,
            f"За прошедшие {days} дн. в этом чате сообщений не было."
        )
        return

    # Собираем все сообщения в одну строку
    chat_text = "\n".join(f"{row['user_name']}: {row['text']}"
                          for row in messages)

    # 2) Собираем усиленный промпт
    prompt = f"""
Ниже приведена переписка (за последние {days} дней) в рабочей группе.

Тебе нужно сделать **глубокий и результативный анализ**, максимально **прикладной** и **ориентированный на командную динамику и менеджмент**.
**Формат:** каждый раздел — в теге <code>...</code>, а сам анализ — в теге <pre>...</pre>.
Примеры (обезличенные), рекомендации, поведенческие паттерны обязательны.

1) <code>Анализ тональности и скрытых эмоций</code>
<pre>
- Определи эмоциональный фон (радость, напряжение, усталость, раздражение).
- Есть ли скрытое недовольство, сарказм, апатия?
- Приведи конкретные реплики для иллюстрации.
</pre>

2) <code>Темы, поднимающие активность или апатию</code>
<pre>
- Какие темы оживили чат?
- Какие темы были проигнорированы?
- Какие типы сообщений стимулируют инициативу или отторжение?
</pre>

3) <code>Проблемные точки и микро-конфликты</code>
<pre>
- Вспышки раздражения, спорные утверждения, игнор.
- Кто гасил конфликт, кто усиливал, кто молчал?
- Как это повлияло на атмосферу?
</pre>

4) <code>Коммуникативные сбои</code>
<pre>
- Где возникало непонимание, повтор темы?
- Были ли задачи без реакции?
- Были ли дублирования, недоговорённости?
</pre>

5) <code>Поведенческий кластеринг участников</code>
<pre>
- Кто формирует повестку (лидеры)?
- Кто выполняет (исполнители)?
- Кто сомневается и тормозит (скептики)?
- Кто отключён (молчуны)?
- Кто поддерживает, шутит (модераторы)?
+ Пример по 1 сообщению от каждой категории.
</pre>

6) <code>Контекстная усталость и признаки перегрузки</code>
<pre>
- Жалобы, эмоциональное выгорание, апатия?
- Кто чаще всего выглядит «перегруженным»?
- Есть ли сигналы, что кто-то «тащит всё» или не справляется?
</pre>

7) <code>Признаки продуктивности</code>
<pre>
- Есть ли отчёты о выполненных задачах?
- Упоминаются ли дедлайны, соблюдение сроков?
</pre>

8) <code>Качество и культура общения</code>
<pre>
- Есть ли грубость, пассивная агрессия, мат?
- Насколько вежлив и конструктивен тон общения?
</pre>

9) <code>Рекомендации</code>
<pre>
- Чёткие шаги по улучшению коммуникации, разгрузке, вовлечённости.
- По 2–4 конкретных предложения на каждый выявленный недостаток.
</pre>

Текст переписки:
{chat_text}
"""

    # 3) Получаем от GPT-4 анализ
    report = await generate_analysis_text(prompt)
    if not report:
        await bot.send_message(group_id, "Ошибка: не удалось получить отчёт от GPT.")
        return

    # 4) Разбиваем на куски и отправляем (HTML-режим)
    await send_long_html(bot, group_id, report)


async def send_long_html(bot: Bot, chat_id: int, text: str, chunk_size=4000):
    """
    Дробим длинный текст и отправляем parse_mode=HTML.
    """
    text = fix_html_tags(text.strip())
    # Разбиваем на куски размером chunk_size символов
    chunks = textwrap.wrap(text, width=chunk_size, replace_whitespace=False)
    for chunk in chunks:
        chunk = fix_html_tags(chunk)
        await bot.send_message(chat_id, chunk, parse_mode="HTML")


def fix_html_tags(text: str) -> str:
    """
    Простейшая функция для балансировки тегов <pre>...</pre>.
    """
    text = text.strip()
    opens = text.count("<pre>")
    closes = text.count("</pre>")
    if opens > closes:
        diff = opens - closes
        text += "</pre>" * diff
    elif closes > opens:
        diff = closes - opens
        for _ in range(diff):
            idx = text.rfind("</pre>")
            if idx >= 0:
                text = text[:idx] + text[idx + 6:]
    return text


async def send_reports_for_all_groups(bot: Bot):
    """
    Бегает по VECTOR_GROUP_IDS и шлёт отчёты за 1 день.
    (можно подвесить на планировщик)
    """
    for group_id in VECTOR_GROUP_IDS:
        try:
            await send_report_for_period(bot, group_id, days=1)
        except Exception as e:
            logger.exception(f"Ошибка при отчёте для группы {group_id}: {e}")
