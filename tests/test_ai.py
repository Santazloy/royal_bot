# tests/test_ai.py
import sys
import os
import subprocess
import pytest
from unittest.mock import patch
from ai import list_models

@pytest.mark.asyncio
async def test_list_models_missing_key():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
            list_models()

@pytest.mark.asyncio
async def test_list_models_invalid_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "invalid-key")
    with pytest.raises(Exception):
        list_models()

def test_ai_script_run_no_key():
    """
    Интеграционный тест: запуск ai.py без ключа
    """
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)

    result = subprocess.run(
        [sys.executable, "ai.py"],  # Используем абсолютный путь к текущему интерпретатору
        capture_output=True,
        text=True,
        env=env
    )
    assert "OPENAI_API_KEY is not set" in result.stdout or "Error:" in result.stdout
