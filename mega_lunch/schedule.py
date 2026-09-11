from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import threading
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from uuid import uuid4


DEFAULT_LUNCH_TIME = dt.time(hour=12)
LUNCH_DURATION = dt.timedelta(hours=1, minutes=10)
TIME_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")
LUNCH_TIME_KEY = "lunch"
WORK_END_TIME_KEY = "work_end"


class HungerPhase(Enum):
    WEEKEND = auto()
    BEFORE_LUNCH = auto()
    LUNCH = auto()
    WORK_END_UNSET = auto()
    BEFORE_WORK_END = auto()
    AFTER_WORK_END = auto()


@dataclass(frozen=True)
class GuildSchedule:
    lunch_time: dt.time = DEFAULT_LUNCH_TIME
    work_end_time: dt.time | None = None


@dataclass(frozen=True)
class HungerStatus:
    phase: HungerPhase
    remaining_minutes: int | None = None


def parse_clock_time(value: str) -> dt.time:
    """Parse a zero-padded 24-hour clock time."""
    if TIME_PATTERN.fullmatch(value) is None:
        raise ValueError("시간은 HH:MM 형식이어야 합니다.")
    hour, minute = (int(part) for part in value.split(":"))
    return dt.time(hour=hour, minute=minute)


def hunger_status(now: dt.datetime, schedule: GuildSchedule) -> HungerStatus:
    """Classify the current hunger response using the guild's daily schedule."""
    if now.weekday() >= 5:
        return HungerStatus(HungerPhase.WEEKEND)

    lunch_start = dt.datetime.combine(
        now.date(),
        schedule.lunch_time,
        tzinfo=now.tzinfo,
    )
    lunch_end = lunch_start + LUNCH_DURATION
    if now < lunch_start:
        return HungerStatus(
            HungerPhase.BEFORE_LUNCH,
            _remaining_minutes(now, lunch_start),
        )
    if now < lunch_end:
        return HungerStatus(HungerPhase.LUNCH)
    if schedule.work_end_time is None:
        return HungerStatus(HungerPhase.WORK_END_UNSET)

    work_end = dt.datetime.combine(
        now.date(),
        schedule.work_end_time,
        tzinfo=now.tzinfo,
    )
    if now < work_end:
        return HungerStatus(
            HungerPhase.BEFORE_WORK_END,
            _remaining_minutes(now, work_end),
        )
    return HungerStatus(HungerPhase.AFTER_WORK_END)


def _remaining_minutes(now: dt.datetime, target: dt.datetime) -> int:
    return math.ceil((target - now).total_seconds() / 60)


def format_remaining_minutes(total_minutes: int) -> str:
    """Format a positive minute count for a Korean countdown message."""
    if total_minutes <= 0:
        raise ValueError("남은 시간은 1분 이상이어야 합니다.")
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}시간 {minutes}분"
    if hours:
        return f"{hours}시간"
    return f"{minutes}분"


class GuildScheduleStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def get(self, guild_id: int) -> GuildSchedule:
        with self._lock:
            values = self._read().get(str(guild_id), {})
        lunch_time = self._time_or_default(
            values.get(LUNCH_TIME_KEY),
            DEFAULT_LUNCH_TIME,
        )
        return GuildSchedule(
            lunch_time=lunch_time or DEFAULT_LUNCH_TIME,
            work_end_time=self._time_or_default(values.get(WORK_END_TIME_KEY), None),
        )

    def set_lunch_time(self, guild_id: int, value: dt.time) -> None:
        self._set(guild_id, LUNCH_TIME_KEY, value)

    def set_work_end_time(self, guild_id: int, value: dt.time) -> None:
        self._set(guild_id, WORK_END_TIME_KEY, value)

    @staticmethod
    def _time_or_default(value: str | None, default: dt.time | None) -> dt.time | None:
        if value is None:
            return default
        try:
            return parse_clock_time(value)
        except ValueError:
            return default

    def _set(self, guild_id: int, key: str, value: dt.time) -> None:
        with self._lock:
            values = self._read()
            guild_values = values.setdefault(str(guild_id), {})
            guild_values[key] = value.strftime("%H:%M")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
            try:
                temporary.write_text(
                    json.dumps(values, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8",
                )
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)

    def _read(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}

        values: dict[str, dict[str, str]] = {}
        for guild_id, guild_values in data.items():
            if not isinstance(guild_id, str) or not isinstance(guild_values, dict):
                continue
            values[guild_id] = {
                key: value
                for key, value in guild_values.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        return values
