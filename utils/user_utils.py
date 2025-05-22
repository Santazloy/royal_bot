# utils/user_utils.py

from constants.booking_const import LANG_DEFAULT

async def get_user_language(user_id: int) -> str:
    return LANG_DEFAULT