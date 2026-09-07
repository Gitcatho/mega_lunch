from __future__ import annotations

import datetime as dt

from .calendar import WeekKey, relative_week


KST_OFFSET = dt.timezone(dt.timedelta(hours=9), name="KST")
PREFETCH_TIME = dt.time(hour=9, tzinfo=KST_OFFSET)
SATURDAY = 5


def scheduled_prefetch_week(today: dt.date) -> WeekKey | None:
    """Return the following menu week only on the scheduled weekday."""
    if today.weekday() != SATURDAY:
        return None
    return relative_week(today, 1)
