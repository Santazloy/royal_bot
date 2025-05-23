# tests/handlers/test_idphoto.py

import pytest
from unittest.mock import AsyncMock
from aiogram.types import Message, PhotoSize
from handlers.idphoto import cmd_id_photo


@pytest.mark.asyncio
async def test_cmd_id_photo_with_photo():
    msg = AsyncMock(spec=Message)
    photo = AsyncMock(spec=PhotoSize)
    photo.file_id = "abc123"
    msg.photo = [photo, photo, photo]  # simulate three sizes
    await cmd_id_photo(msg)
    msg.answer.assert_awaited_with(
        "file_id вашего фото:\n<code>abc123</code>", parse_mode="HTML"
    )


@pytest.mark.asyncio
async def test_cmd_id_photo_without_photo():
    msg = AsyncMock(spec=Message)
    msg.photo = []
    await cmd_id_photo(msg)
    msg.answer.assert_awaited_with("Вы не прикрепили фото к команде /id.")
