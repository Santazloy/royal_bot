# handlers/booking/data_manager.py

from typing import Dict, Any
from utils.time_utils import get_adjacent_time_slots

class BookingDataManager:
    def __init__(self, initial_groups: Dict[str, Any]):
        self.groups = {k: v.copy() for k, v in initial_groups.items()}

    def list_group_keys(self):
        return list(self.groups.keys())

    def get_group_info(self, group_key: str) -> Dict[str, Any]:
        return self.groups[group_key]

    def book_slot(self, group_key: str, day: str, slot: str, user_id: int):
        ginfo = self.groups[group_key]
        ginfo["booked_slots"][day].append(slot)
        ginfo["slot_bookers"][(day, slot)] = user_id
        ginfo["time_slot_statuses"][(day, slot)] = "booked"
        for adj in get_adjacent_time_slots(slot):
            if adj not in ginfo["booked_slots"][day]:
                ginfo["unavailable_slots"][day].add(adj)
                ginfo["time_slot_statuses"][(day, adj)] = "unavailable"
                ginfo["slot_bookers"][(day, adj)] = user_id