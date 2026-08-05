from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

import requests
from PIL import Image, ImageFilter, UnidentifiedImageError

from .calendar import WeekKey
from .models import CachedMenu, MenuPost
from .settings import Settings


log = logging.getLogger(__name__)
CACHE_FORMAT_VERSION = 2

# 식단표에서 날짜 행과 점심(Self) 영역을 구분하는 긴 가로선을 찾기 위한 범위.
# 주간 이미지의 위쪽 여백은 달라질 수 있지만 표 디자인과 행 비율은 일정하다.
TOP_RULE_SEARCH_RANGE = (0.18, 0.28)
BOTTOM_RULE_SEARCH_RANGE = (0.40, 0.56)
HORIZONTAL_RULE_DARK_THRESHOLD = 110
HORIZONTAL_RULE_MIN_COVERAGE = 0.72
NEARBY_RULE_GAP = 15


class MenuImageError(RuntimeError):
    pass


class MenuCache:
    def __init__(self, settings: Settings):
        self.settings = settings
        Image.MAX_IMAGE_PIXELS = settings.max_image_pixels

    def load(self, week: WeekKey) -> CachedMenu | None:
        directory = self._week_dir(week)
        manifest_path = directory / "menu.json"
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if data.get("version") != CACHE_FORMAT_VERSION:
                return None
            full_image = directory / data["full_image"]
            day_images = tuple(directory / name for name in data["day_images"])
            if not full_image.is_file() or len(day_images) != 5:
                return None
            if not all(path.is_file() for path in day_images):
                return None
            return CachedMenu(
                week=week,
                title=data["title"],
                published_at=self._parse_datetime(data["published_at"]),
                page_url=data["page_url"],
                full_image=full_image,
                day_images=day_images,
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def create(self, week: WeekKey, post: MenuPost) -> CachedMenu:
        image_bytes = self._download(post)
        directory = self._week_dir(week)
        directory.mkdir(parents=True, exist_ok=True)

        try:
            full_name, day_names = self._write_images(directory, image_bytes)
            manifest = {
                "version": CACHE_FORMAT_VERSION,
                "title": post.title,
                "published_at": post.published_at.isoformat(),
                "page_url": post.page_url,
                "full_image": full_name,
                "day_images": day_names,
            }
            self._atomic_text(directory / "menu.json", json.dumps(manifest, ensure_ascii=False))
        except Exception:
            log.exception("메뉴 이미지 캐시 생성 실패: %s", week)
            raise

        cached = self.load(week)
        if cached is None:
            raise MenuImageError("생성한 메뉴 캐시를 확인하지 못했습니다.")
        return cached

    def keep_only(self, weeks: set[WeekKey]) -> None:
        root = self.settings.cache_dir
        if not root.exists():
            return
        allowed = {str(week) for week in weeks}
        for path in root.iterdir():
            if not path.is_dir() or not path.name.startswith("20") or path.name in allowed:
                continue
            for child in path.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            try:
                path.rmdir()
            except OSError:
                pass

    def _download(self, post: MenuPost) -> bytes:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Referer": post.page_url,
        }
        for url in post.image_urls:
            try:
                with requests.get(
                    url,
                    headers=headers,
                    stream=True,
                    timeout=self.settings.request_timeout,
                ) as response:
                    response.raise_for_status()
                    expected = int(response.headers.get("Content-Length", "0"))
                    if expected > self.settings.max_download_bytes:
                        continue

                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_content(64 * 1024):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > self.settings.max_download_bytes:
                            chunks = []
                            break
                        chunks.append(chunk)
                    if chunks:
                        return b"".join(chunks)
            except (requests.RequestException, ValueError):
                log.warning("메뉴 이미지 다운로드 후보 실패: %s", url)
        raise MenuImageError("식단표 이미지를 다운로드하지 못했습니다.")

    def _write_images(self, directory: Path, image_bytes: bytes) -> tuple[str, list[str]]:
        try:
            with Image.open(io.BytesIO(image_bytes)) as source:
                source.load()
                width, height = source.size
                if width * height > self.settings.max_image_pixels:
                    raise MenuImageError("식단표 이미지의 해상도가 허용 범위를 넘었습니다.")

                source_format = (source.format or "JPEG").upper()
                extension = ".png" if source_format == "PNG" else ".jpg"
                full_name = f"full{extension}"
                self._atomic_bytes(directory / full_name, image_bytes)

                day_names: list[str] = []
                for weekday in range(5):
                    day_name = f"day-{weekday}.png"
                    cropped = self._crop_day(source, weekday)
                    try:
                        self._atomic_image(directory / day_name, cropped)
                    finally:
                        cropped.close()
                    day_names.append(day_name)
                return full_name, day_names
        except (UnidentifiedImageError, OSError) as exc:
            raise MenuImageError("다운로드한 파일이 올바른 이미지가 아닙니다.") from exc

    def _crop_day(self, source: Image.Image, weekday: int) -> Image.Image:
        width, height = source.size
        top, bottom = self._lunch_vertical_bounds(source)
        table_left = width * self.settings.crop_left
        column_width = width * self.settings.crop_width / 5
        left = round(table_left + column_width * weekday)
        right = round(table_left + column_width * (weekday + 1))

        if left < 0 or top < 0 or right > width or bottom > height or left >= right or top >= bottom:
            raise MenuImageError("요일별 이미지 자르기 설정이 유효하지 않습니다.")

        cropped = source.crop((left, top, right, bottom)).convert("RGB")
        if cropped.width >= self.settings.day_image_width:
            return cropped

        scale = self.settings.day_image_width / cropped.width
        resized = cropped.resize(
            (self.settings.day_image_width, round(cropped.height * scale)),
            Image.Resampling.LANCZOS,
        )
        cropped.close()
        sharpened = resized.filter(ImageFilter.UnsharpMask(radius=1.2, percent=90, threshold=2))
        resized.close()
        return sharpened

    def _lunch_vertical_bounds(self, source: Image.Image) -> tuple[int, int]:
        """날짜 행 시작부터 Take-Out 행 직전까지의 세로 경계를 찾는다."""
        height = source.height
        fallback_top = round(height * self.settings.crop_top)
        fallback_bottom = fallback_top + round(height * self.settings.crop_height)

        rules = self._horizontal_rules(source)
        top_candidates = [
            y
            for y in rules
            if height * TOP_RULE_SEARCH_RANGE[0] <= y <= height * TOP_RULE_SEARCH_RANGE[1]
        ]
        bottom_candidates = [
            y
            for y in rules
            if height * BOTTOM_RULE_SEARCH_RANGE[0] <= y <= height * BOTTOM_RULE_SEARCH_RANGE[1]
        ]

        if not top_candidates or not bottom_candidates:
            log.warning("식단표 가로선 검출 실패 — 설정된 크롭 비율을 사용합니다.")
            return fallback_top, fallback_bottom

        # 상단 배너의 아래 선과 표의 시작 선은 6~10px 간격으로 붙어 있다.
        # 첫 번째 선과 가까운 후보 중 마지막 선이 실제 날짜 행 시작점이다.
        first_top = min(top_candidates)
        top = max(y for y in top_candidates if y - first_top <= NEARBY_RULE_GAP)

        # 점심 영역 아래에는 Take-Out, 도시락 순서로 경계선이 나타난다.
        # 탐색 범위에서 첫 번째 선이 점심 영역의 끝이다.
        bottom = min(bottom_candidates)

        if top >= bottom:
            log.warning("식단표 가로선 순서가 올바르지 않음 — 설정된 크롭 비율을 사용합니다.")
            return fallback_top, fallback_bottom
        return top, bottom

    def _horizontal_rules(self, source: Image.Image) -> list[int]:
        """메뉴 열 폭의 대부분을 가로지르는 어두운 수평선의 y 좌표를 반환한다."""
        width, height = source.size
        x_start = max(0, round(width * self.settings.crop_left))
        x_end = min(width, round(width * (self.settings.crop_left + self.settings.crop_width)))
        scan_width = x_end - x_start
        minimum_dark_pixels = round(scan_width * HORIZONTAL_RULE_MIN_COVERAGE)

        grayscale = source.convert("L")
        try:
            matching_rows: list[int] = []
            search_start = round(height * TOP_RULE_SEARCH_RANGE[0])
            search_end = round(height * BOTTOM_RULE_SEARCH_RANGE[1])
            for y in range(search_start, search_end + 1):
                histogram = grayscale.crop((x_start, y, x_end, y + 1)).histogram()
                dark_pixels = sum(histogram[:HORIZONTAL_RULE_DARK_THRESHOLD])
                if dark_pixels >= minimum_dark_pixels:
                    matching_rows.append(y)
        finally:
            grayscale.close()

        # JPEG 압축이나 두꺼운 테두리 때문에 연속 검출된 행은 하나로 합친다.
        rules: list[int] = []
        previous_y: int | None = None
        for y in matching_rows:
            if previous_y is None or y > previous_y + 1:
                rules.append(y)
            previous_y = y
        return rules

    def _week_dir(self, week: WeekKey) -> Path:
        return self.settings.cache_dir / str(week)

    @staticmethod
    def _parse_datetime(value: str):
        from datetime import datetime

        return datetime.fromisoformat(value)

    @staticmethod
    def _temporary_path(destination: Path) -> Path:
        return destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")

    def _atomic_text(self, destination: Path, content: str) -> None:
        temporary = self._temporary_path(destination)
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, destination)

    def _atomic_bytes(self, destination: Path, content: bytes) -> None:
        temporary = self._temporary_path(destination)
        temporary.write_bytes(content)
        os.replace(temporary, destination)

    def _atomic_image(self, destination: Path, image: Image.Image) -> None:
        temporary = self._temporary_path(destination)
        try:
            image.save(temporary, format="PNG", optimize=True)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
