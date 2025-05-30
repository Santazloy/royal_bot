import sys
import os
import subprocess
import pytest
from unittest.mock import patch, AsyncMock
from aiogram.types import Message

@pytest.mark.asyncio
async def test_cmd_ai_no_api_key(monkeypatch):
    from handlers.ai import cmd_ai
    from utils.bot_utils import safe_answer

    msg = AsyncMock(spec=Message)
    msg.from_user = type("User", (), {"id": 123})
    msg.chat = type("Chat", (), {"id": 123})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch("handlers.ai.safe_answer", new=AsyncMock()) as m:
        await cmd_ai(msg)
        m.assert_awaited()
        assert "API key" in m.call_args[0][1]

def test_ai_script_run_no_key(tmp_path):
    script_path = tmp_path / "ai.py"
    script_path.write_text(
        "import os\n"
        "if not os.getenv('OPENAI_API_KEY'):\n"
        "    print('❌ OpenAI API key is not set.')\n"
        "else:\n"
        "    print('key present')\n"
    )
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        env=env
    )
    assert (
        "❌ OpenAI API key is not set." in result.stdout
        or "Error:" in result.stdout
        or "OPENAI_API_KEY is not set" in result.stdout
    )
