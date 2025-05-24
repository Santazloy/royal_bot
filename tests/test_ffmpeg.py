# tests/test_ffmpeg.py

import importlib

def test_ffmpeg_module_executes():
    assert importlib.import_module("ffmpeg") is not None
