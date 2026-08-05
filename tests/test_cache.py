import unittest

from PIL import Image, ImageDraw

from mega_lunch.cache import MenuCache
from mega_lunch.settings import Settings


def test_settings() -> Settings:
    from pathlib import Path

    return Settings(
        discord_token="test",
        blog_id="test",
        category_no="1",
        title_keyword="menu",
        cache_dir=Path("cache"),
        request_timeout=1,
        max_download_bytes=1024,
        max_image_pixels=2_000_000,
        day_image_width=800,
        crop_top=0.232,
        crop_height=0.25,
        crop_left=0.169,
        crop_width=0.81,
    )


class LunchCropBoundsTests(unittest.TestCase):
    def test_detects_date_header_and_excludes_takeout(self):
        image = Image.new("RGB", (1000, 1000), "white")
        draw = ImageDraw.Draw(image)

        # 상단 배너 아래 선, 날짜 행 시작 선, 점심 종료/Take-Out 시작 선,
        # Take-Out 종료/도시락 시작 선을 실제 식단표와 같은 순서로 그린다.
        for y in (210, 219, 463, 538):
            draw.line((169, y, 979, y), fill="black", width=1)

        cache = MenuCache(test_settings())
        self.assertEqual(cache._lunch_vertical_bounds(image), (219, 463))
        image.close()

    def test_falls_back_to_configured_ratios_without_rules(self):
        image = Image.new("RGB", (1000, 1000), "white")
        cache = MenuCache(test_settings())
        self.assertEqual(cache._lunch_vertical_bounds(image), (232, 482))
        image.close()


if __name__ == "__main__":
    unittest.main()
