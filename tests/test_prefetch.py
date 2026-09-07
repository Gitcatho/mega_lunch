import datetime as dt
import unittest

from mega_lunch.calendar import WeekKey
from mega_lunch.prefetch import PREFETCH_TIME, scheduled_prefetch_week


class MenuPrefetchTests(unittest.TestCase):
    def test_returns_next_week_on_saturday(self):
        self.assertEqual(
            scheduled_prefetch_week(dt.date(2026, 9, 12)),
            WeekKey(2026, 38),
        )

    def test_skips_other_weekdays(self):
        self.assertIsNone(scheduled_prefetch_week(dt.date(2026, 9, 11)))

    def test_prefetch_time_is_nine_am_kst(self):
        self.assertEqual(PREFETCH_TIME.hour, 9)
        self.assertEqual(PREFETCH_TIME.utcoffset(), dt.timedelta(hours=9))


if __name__ == "__main__":
    unittest.main()
