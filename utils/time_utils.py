# utils/time_utils.py

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List

SLOT_TZ = ZoneInfo("Asia/Shanghai")

def generate_daily_time_slots() -> List[str]:
    return [
        "12:00","12:30","13:00","13:30","14:00","14:30","15:00","15:30",
        "16:00","16:30","17:00","17:30","18:00","18:30","19:00","19:30",
        "20:00","20:30","21:00","21:30","22:00","22:30","23:00","23:30",
        "00:00","00:30","01:00","01:30","02:00"
    ]

def get_adjacent_time_slots(slot: str) -> List[str]:
    slots = generate_daily_time_slots()
    if slot not in slots:
        return []
    i = slots.index(slot)
    neighbours = []
    if i > 0:
        neighbours.append(slots[i-1])
    if i < len(slots)-1:
        neighbours.append(slots[i+1])
    return neighbours

def get_slot_datetime_shanghai(day: str, slot: str) -> str:
    now = datetime.now(SLOT_TZ)
    if day.lower() == "завтра":
        now += timedelta(days=1)
    hh, mm = slot.split(":")
    dt = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    return dt.isoformat()