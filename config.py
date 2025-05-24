# config.py
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDATABASE = os.getenv("PGDATABASE")
DATABASE_URL = os.getenv("DATABASE_URL")
FFMPEG_CMD = os.getenv("FFMPEG_PATH", "ffmpeg")
GROUP_IDS = [
    -1002503654146,
    -1002569987326
]

ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def is_user_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
