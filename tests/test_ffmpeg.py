# tests/test_ffmpeg.py

import subprocess

def test_ffmpeg_version():
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    assert "ffmpeg version" in result.stdout
