# handlers/idphoto.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

router = Router()

# Store last bot-sent message per chat
last_bot_message: dict[int, int] = {}

async def safe_answer(entity, text: str, **kwargs):
    if hasattr(entity, "message") and hasattr(entity.message, "chat"):
        chat_id = entity.message.chat.id
    else:
        chat_id = entity.chat.id

    prev = last_bot_message.get(chat_id)
    if prev:
        try:
            await entity.bot.delete_message(chat_id=chat_id, message_id=prev)
        except:
            pass

    if hasattr(entity, "message") and hasattr(entity.message, "answer"):
        sent = await entity.message.answer(text, **kwargs)
    else:
        sent = await entity.answer(text, **kwargs)

    last_bot_message[chat_id] = sent.message_id
    return sent

class IDPhotoStates(StatesGroup):
    waiting_photo = State()

@router.callback_query(F.data == "leonard_photo_id")
async def ask_id_photo(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback, "📷 Отправьте фото, чтобы получить ID.")
    await state.set_state(IDPhotoStates.waiting_photo)

@router.message(StateFilter(IDPhotoStates.waiting_photo), F.photo)
async def receive_photo(message: Message, state: FSMContext):
    largest_photo = message.photo[-1]
    await safe_answer(message, f"file_id вашего фото:\n<code>{largest_photo.file_id}</code>", parse_mode="HTML")
    await state.clear()

@router.message(Command("id"))
async def cmd_id_photo(message: Message):
    if message.photo:
        largest_photo = message.photo[-1]
        await safe_answer(message, f"file_id вашего фото:\n<code>{largest_photo.file_id}</code>", parse_mode="HTML")
    else:
        await safe_answer(message, "Вы не прикрепили фото к команде /id.")
