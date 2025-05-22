# handlers/booking/data_manager.py

import logging
from typing import Dict, Any
from utils.time_utils import get_adjacent_time_slots

logger = logging.getLogger(__name__)

class BookingDataManager:
    """
    Менеджер локальной in-memory структуры groups_data:
      - booked_slots
      - slot_bookers
      - time_slot_statuses
      - unavailable_slots
    """
    def __init__(self, groups: Dict[str, Any]):
        # храним прямую ссылку на константу constants.booking_const.groups_data
        self.groups = groups

    def list_group_keys(self):
        return list(self.groups.keys())

    def get_group_info(self, group_key: str) -> Dict[str, Any]:
        return self.groups[group_key]

    def book_slot(self, group_key: str, day: str, slot: str, user_id: int):
        g = self.groups[group_key]
        # 1) отмечаем сам слот
        g["booked_slots"].setdefault(day, []).append(slot)
        g["slot_bookers"][(day, slot)] = user_id
        g["time_slot_statuses"][(day, slot)] = "booked"
        # 2) блокируем соседние
        for adj in get_adjacent_time_slots(slot):
            if adj not in g["booked_slots"].get(day, []):
                g["unavailable_slots"].setdefault(day, set()).add(adj)
                g["time_slot_statuses"][(day, adj)] = "unavailable"
                g["slot_bookers"][(day, adj)] = user_id
