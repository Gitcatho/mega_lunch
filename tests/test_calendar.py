import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from mega_lunch.calendar import (
    WeekKey,
    is_serving_day,
    menu_week_for_post,
    relative_day,
    relative_week,
)


KST = ZoneInfo("Asia/Seoul")


class WeekKeyTests(unittest.TestCase):
    def test_post_maps_to_following_week(self):
        published = dt.datetime(2026, 7, 17, 9, 0, tzinfo=KST)
        self.assertEqual(menu_week_for_post(published), WeekKey(2026, 30))

    def test_early_post_still_maps_by_one_full_week(self):
        published = dt.datetime(2026, 7, 16, 9, 0, tzinfo=KST)
        self.assertEqual(menu_week_for_post(published), WeekKey(2026, 30))

    def test_year_boundary_uses_iso_year(self):
        published = dt.datetime(2026, 12, 25, 9, 0, tzinfo=KST)
        self.assertEqual(menu_week_for_post(published), WeekKey(2026, 53))

    def test_relative_week_crosses_year_boundary(self):
        self.assertEqual(relative_week(dt.date(2026, 12, 31), 1), WeekKey(2027, 1))


class ServingDayTests(unittest.TestCase):
    def test_weekdays_are_serving_days(self):
        monday = dt.date(2026, 7, 20)
        self.assertTrue(is_serving_day(monday))
        self.assertTrue(is_serving_day(relative_day(monday, 4)))

    def test_weekend_is_not_a_serving_day(self):
        saturday = dt.date(2026, 7, 25)
        self.assertFalse(is_serving_day(saturday))
        self.assertFalse(is_serving_day(relative_day(saturday, 1)))

    def test_sunday_tomorrow_uses_next_week(self):
        sunday = dt.date(2026, 7, 26)
        monday = relative_day(sunday, 1)
        self.assertTrue(is_serving_day(monday))
        self.assertEqual(WeekKey.from_date(monday), WeekKey(2026, 31))


if __name__ == "__main__":
    unittest.main()
