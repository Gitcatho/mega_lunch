import datetime as dt
import tempfile
import unittest
from pathlib import Path

from mega_lunch.schedule import (
    DEFAULT_LUNCH_TIME,
    GuildSchedule,
    GuildScheduleStore,
    HungerPhase,
    format_remaining_minutes,
    hunger_status,
    parse_clock_time,
)
from mega_lunch.settings import KST


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.schedule = GuildSchedule(dt.time(12, 50), dt.time(17, 50))

    def test_parses_zero_padded_24_hour_time(self):
        self.assertEqual(parse_clock_time("12:50"), dt.time(hour=12, minute=50))

    def test_rejects_invalid_time_formats(self):
        for value in ("2:50", "12:5", "24:00", "12:60", "noon"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_clock_time(value)

    def test_reports_time_until_lunch(self):
        now = dt.datetime(2026, 9, 11, 11, 30, tzinfo=KST)
        status = hunger_status(now, self.schedule)
        self.assertEqual(status.phase, HungerPhase.BEFORE_LUNCH)
        self.assertEqual(status.remaining_minutes, 80)

    def test_reports_lunch_for_seventy_minutes(self):
        lunch_start = dt.datetime(2026, 9, 11, 12, 50, tzinfo=KST)
        before_end = dt.datetime(2026, 9, 11, 13, 59, 59, tzinfo=KST)
        self.assertEqual(hunger_status(lunch_start, self.schedule).phase, HungerPhase.LUNCH)
        self.assertEqual(hunger_status(before_end, self.schedule).phase, HungerPhase.LUNCH)

    def test_reports_time_until_work_end_after_lunch(self):
        lunch_end = dt.datetime(2026, 9, 11, 14, 0, tzinfo=KST)
        status = hunger_status(lunch_end, self.schedule)
        self.assertEqual(status.phase, HungerPhase.BEFORE_WORK_END)
        self.assertEqual(status.remaining_minutes, 230)

    def test_reports_after_work_end(self):
        work_end = dt.datetime(2026, 9, 11, 17, 50, tzinfo=KST)
        self.assertEqual(
            hunger_status(work_end, self.schedule).phase,
            HungerPhase.AFTER_WORK_END,
        )

    def test_reports_day_off_on_weekend(self):
        saturday = dt.datetime(2026, 9, 12, 11, 30, tzinfo=KST)
        self.assertEqual(
            hunger_status(saturday, self.schedule).phase,
            HungerPhase.WEEKEND,
        )

    def test_reports_missing_work_end_after_lunch(self):
        now = dt.datetime(2026, 9, 11, 14, 0, tzinfo=KST)
        status = hunger_status(now, GuildSchedule(dt.time(12, 50)))
        self.assertEqual(status.phase, HungerPhase.WORK_END_UNSET)

    def test_formats_remaining_hours_and_minutes(self):
        self.assertEqual(format_remaining_minutes(80), "1시간 20분")
        self.assertEqual(format_remaining_minutes(60), "1시간")
        self.assertEqual(format_remaining_minutes(15), "15분")


class GuildScheduleStoreTests(unittest.TestCase):
    def test_persists_one_schedule_for_everyone_in_the_guild(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guild-schedules.json"
            store = GuildScheduleStore(path)

            self.assertEqual(store.get(100).lunch_time, DEFAULT_LUNCH_TIME)
            self.assertIsNone(store.get(100).work_end_time)
            store.set_lunch_time(100, dt.time(12, 50))
            store.set_work_end_time(100, dt.time(17, 50))

            reloaded = GuildScheduleStore(path)
            self.assertEqual(
                reloaded.get(100),
                GuildSchedule(dt.time(12, 50), dt.time(17, 50)),
            )
            self.assertEqual(reloaded.get(200), GuildSchedule())


if __name__ == "__main__":
    unittest.main()
