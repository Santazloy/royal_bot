# tests/test_ai.py

import pytest
import importlib

@pytest.mark.skip(reason="OpenAI API key should not be exposed or used in tests.")
def test_openai_list_models():
    with pytest.raises(Exception):
        importlib.import_module("ai")
