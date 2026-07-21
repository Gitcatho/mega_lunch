from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from .calendar import WeekKey


@dataclass(frozen=True)
class MenuPost:
    title: str
    published_at: dt.datetime
    page_url: str
    image_urls: tuple[str, ...]


@dataclass(frozen=True)
class CachedMenu:
    week: WeekKey
    title: str
    published_at: dt.datetime
    page_url: str
    full_image: Path
    day_images: tuple[Path, ...]
