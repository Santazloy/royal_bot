# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# 1) Загрузка .env из того же каталога, где лежит config.py
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 2) Разбор ADMIN_IDS из .env
_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []
for part in _admins.split(","):
    part = part.strip()
    if part.isdigit():
        ADMIN_IDS.append(int(part))

# 3) Отладочный вывод при старте
print(f"Loaded ADMIN_IDS: {ADMIN_IDS}")

def is_user_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
