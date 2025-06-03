# handlers/gpt.py
import os
import time
import uuid
import textwrap
import openai
import aiohttp
import db
from aiogram import Router, Bot
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram import F
from config import TELEGRAM_BOT_TOKEN, OPENAI_API_KEY

router = Router()
openai.api_key = OPENAI_API_KEY

# ──────────────────────────────── Параметры моделей ──────────────────────────────── #
CHAT_MODEL = "gpt-4o"
VISION_MODEL = "gpt-4o-2024-05-13"      # поддерживает image_url
TTS_MODEL = "gpt-4o-mini-tts"
IMAGE_MODEL = "dall-e-3"
IMAGE_SIZE = "1024x1024"
MAX_TG_LEN = 4096                       # лимит символов Telegram

# ──────────────────────────────── Промпт генерации фото ──────────────────────────── #
BASE_REALISM_PROMPT = (
    "{user_prompt}. RAW photo, 8K ultra-realistic, natural cinematic lighting, "
    "sharp focus, high dynamic range, depth of field, extremely detailed textures, "
    "Canon EOS R5, 50 mm f/1.4 lens, no CGI, no illustration, no cartoon"
)

# ──────────────────────────────── Вспом-функции ──────────────────────────────────── #
def split_text(text: str) -> list[str]:
    if len(text) <= MAX_TG_LEN:
        return [text]
    parts: list[str] = []
    for paragraph in text.split("\n\n"):
        wrapped = textwrap.wrap(paragraph, MAX_TG_LEN, break_long_words=False)
        if not wrapped:
            continue
        if parts and len(parts[-1]) + len(wrapped[0]) + 2 <= MAX_TG_LEN:
            parts[-1] += "\n\n" + wrapped[0]
            parts.extend(wrapped[1:])
        else:
            parts.extend(wrapped)
    return parts


async def send_long_md(msg: Message, text: str):
    for chunk in split_text(text):
        await msg.answer(chunk, parse_mode="Markdown")


async def tts(text: str) -> str:
    path = f"{uuid.uuid4()}.mp3"
    async with aiohttp.ClientSession() as s:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": TTS_MODEL, "input": text, "voice": "ash", "format": "mp3"}
        async with s.post("https://api.openai.com/v1/audio/speech", headers=headers, json=payload) as r:
            audio = await r.read()
    with open(path, "wb") as f:
        f.write(audio)
    return path


async def get_file_url(bot: Bot, file_id: str) -> str:
    tg_file = await bot.get_file(file_id)
    return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{tg_file.file_path}"


# ──────────────────────────────── Память GPT ─────────────────────────────────────── #
async def save_message(user_id: int, user_name: str, msg_type: str, content: str):
    await db.db_pool.execute(
        """
        INSERT INTO gpt_memory(user_id, user_name, message_type, content, timestamp)
        VALUES($1, $2, $3, $4, $5)
        """,
        user_id,
        user_name,
        msg_type,
        content,
        int(time.time()),
    )
    await db.db_pool.execute(
        """
        DELETE FROM gpt_memory
        WHERE id IN (
            SELECT id FROM gpt_memory
            WHERE user_id = $1
            ORDER BY timestamp DESC
            OFFSET 20
        )
        """,
        user_id,
    )


async def fetch_context(user_id: int, limit: int = 20) -> list[dict]:
    rows = await db.db_pool.fetch(
        """
        SELECT message_type, content
        FROM gpt_memory
        WHERE user_id = $1
        ORDER BY timestamp ASC
        """,
        user_id,
    )
    ctx: list[dict] = []
    for r in rows[-limit:]:
        if r["message_type"] in {"user_text", "user_voice_text"}:
            ctx.append({"role": "user", "content": r["content"]})
        elif r["message_type"] == "assistant_text":
            ctx.append({"role": "assistant", "content": r["content"]})
    return ctx


# ──────────────────────────────── Команды ────────────────────────────────────────── #
@router.message(Command("gpt_init"))
async def cmd_gpt_init(message: Message):
    await db.create_tables()
    await message.answer("Таблица памяти GPT проверена/создана.")


@router.message(Command("generate"))
async def generate_image(message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    parts = (message.text or "").split(maxsplit=1)
    prompt = parts[1].strip() if len(parts) > 1 else ""
    if not prompt:
        await message.answer("Укажите текст после /generate.")
        return

    await save_message(user_id, user_name, "user_text", prompt)

    ready_prompt = BASE_REALISM_PROMPT.format(user_prompt=prompt)
    resp = await openai.Image.acreate(
        model=IMAGE_MODEL,
        prompt=ready_prompt,
        n=1,
        size=IMAGE_SIZE,
        quality="hd",
        style="natural",
    )
    url = resp["data"][0]["url"]
    await save_message(user_id, user_name, "assistant_image_url", url)
    await message.answer_photo(url)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    prompt = message.text

    await save_message(user_id, user_name, "user_text", prompt)

    ctx = await fetch_context(user_id)
    ctx.append({"role": "system", "content": "Отвечай на русском. Код оборачивай в Markdown ```."})
    ctx.append({"role": "user", "content": prompt})

    resp = await openai.ChatCompletion.acreate(model=CHAT_MODEL, messages=ctx, max_tokens=2048)
    reply = resp.choices[0].message.content
    await save_message(user_id, user_name, "assistant_text", reply)

    await send_long_md(message, reply)


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot):
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    tg_file = await bot.get_file(message.voice.file_id)
    tmp = f"{uuid.uuid4()}.ogg"
    await bot.download_file(tg_file.file_path, tmp)

    with open(tmp, "rb") as f:
        transcription = openai.Audio.transcribe("whisper-1", f)
    os.remove(tmp)
    text = transcription["text"]
    await save_message(user_id, user_name, "user_voice_text", text)

    ctx = await fetch_context(user_id)
    ctx.append({"role": "system", "content": "Отвечай на русском. Код оборачивай в Markdown ```."})
    ctx.append({"role": "user", "content": text})

    resp = await openai.ChatCompletion.acreate(model=CHAT_MODEL, messages=ctx, max_tokens=2048)
    reply = resp.choices[0].message.content
    await save_message(user_id, user_name, "assistant_text", reply)

    mp3 = await tts(reply)
    await save_message(user_id, user_name, "assistant_voice", "[audio]")
    await message.answer_voice(voice=FSInputFile(mp3))
    os.remove(mp3)


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot):
    user_id = message.from_user.id
    user_name = message.from_user.full_name

    url = await get_file_url(bot, message.photo[-1].file_id)
    await save_message(user_id, user_name, "user_image_url", url)

    vision_msgs = [
        {"role": "system", "content": "Опиши изображение на русском кратко и по делу."},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}}]},
    ]
    resp = await openai.ChatCompletion.acreate(model=VISION_MODEL, messages=vision_msgs, max_tokens=1024)
    reply = resp.choices[0].message.content
    await save_message(user_id, user_name, "assistant_text", reply)

    mp3 = await tts(reply)
    await save_message(user_id, user_name, "assistant_voice", "[audio]")
    await message.answer_voice(voice=FSInputFile(mp3))
    os.remove(mp3)


async def on_startup():
    pass  # память создаётся в db.create_tables
