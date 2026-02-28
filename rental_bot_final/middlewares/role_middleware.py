import time
from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import SUPER_ADMIN_ID
from services.user_service import get_user_by_telegram_id
from loguru import logger

# Simple in-memory cache: {telegram_id: (db_user, expire_timestamp)}
# Avoids a DB query on every single message/callback.
# TTL = 30 seconds — user data (name, active status) rarely changes.
_cache: dict[int, tuple] = {}
_CACHE_TTL = 30  # seconds


def _invalidate(telegram_id: int):
    """Call this after activate/deactivate so the cache is cleared immediately."""
    _cache.pop(telegram_id, None)


class RoleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            tg_id = user.id
            data["is_super_admin"] = (tg_id == SUPER_ADMIN_ID)

            cached = _cache.get(tg_id)
            if cached and time.monotonic() < cached[1]:
                data["db_user"] = cached[0]
            else:
                db_user = await get_user_by_telegram_id(tg_id)
                _cache[tg_id] = (db_user, time.monotonic() + _CACHE_TTL)
                data["db_user"] = db_user
                logger.debug(f"User {tg_id} fetched from DB | active={db_user['is_active'] if db_user else False}")

        return await handler(event, data)
