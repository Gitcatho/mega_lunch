from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


WEEKDAY_NAMES = ("월요일", "화요일", "수요일", "목요일", "금요일")


@dataclass(frozen=True, order=True)
class WeekKey:
    year: int
    week: int

    @classmethod
    def from_date(cls, value: dt.date) -> "WeekKey":
        iso = value.isocalendar()
        return cls(iso.year, iso.week)

    def __str__(self) -> str:
        return f"{self.year}-W{self.week:02d}"


def menu_week_for_post(published_at: dt.datetime) -> WeekKey:
    """A cafeteria post announces the menu for the following ISO week."""
    return WeekKey.from_date((published_at + dt.timedelta(days=7)).date())


def relative_week(today: dt.date, offset: int = 0) -> WeekKey:
    return WeekKey.from_date(today + dt.timedelta(weeks=offset))


def relative_day(today: dt.date, offset: int) -> dt.date:
    return today + dt.timedelta(days=offset)


def is_serving_day(value: dt.date) -> bool:
    return value.weekday() < len(WEEKDAY_NAMES)
