from __future__ import annotations

import asyncio
import datetime as dt

from .cache import MenuCache
from .calendar import WeekKey, relative_week
from .models import CachedMenu
from .settings import KST, Settings
from .source import NaverBlogMenuSource


class MenuNotPublished(RuntimeError):
    pass


class MenuService:
    def __init__(self, settings: Settings):
        self.source = NaverBlogMenuSource(settings)
        self.cache = MenuCache(settings)
        self._lock = asyncio.Lock()

    async def get(self, week: WeekKey) -> CachedMenu:
        cached = await asyncio.to_thread(self.cache.load, week)
        if cached is not None:
            return cached

        async with self._lock:
            cached = await asyncio.to_thread(self.cache.load, week)
            if cached is not None:
                return cached

            post = await asyncio.to_thread(self.source.find_week, week)
            if post is None:
                raise MenuNotPublished(f"{week} 식단표가 아직 게시되지 않았습니다.")
            cached = await asyncio.to_thread(self.cache.create, week, post)
            await asyncio.to_thread(self._cleanup)
            return cached

    def _cleanup(self) -> None:
        today = dt.datetime.now(KST).date()
        self.cache.keep_only({relative_week(today), relative_week(today, 1)})
