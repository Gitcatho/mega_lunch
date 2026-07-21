from __future__ import annotations

import datetime as dt
import html
import logging
from typing import Any

import requests
from bs4 import BeautifulSoup

from .calendar import WeekKey, menu_week_for_post
from .models import MenuPost
from .settings import KST, Settings


log = logging.getLogger(__name__)


class MenuSourceError(RuntimeError):
    pass


class NaverBlogMenuSource:
    """Finds weekly cafeteria posts and their first content image."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Referer": f"https://m.blog.naver.com/{settings.blog_id}",
            }
        )

    def find_week(self, target: WeekKey) -> MenuPost | None:
        items = self._recent_posts()
        for item in items:
            title = self._plain_title(item.get("titleWithInspectMessage", ""))
            if self.settings.title_keyword not in title:
                continue

            published_at = self._published_at(item)
            if menu_week_for_post(published_at) != target:
                continue

            log_no = str(item.get("logNo", "")).strip()
            if not log_no:
                continue
            page_url = (
                "https://blog.naver.com/PostView.naver"
                f"?blogId={self.settings.blog_id}&logNo={log_no}"
            )
            image_urls = self._content_images(page_url)
            if not image_urls:
                raise MenuSourceError("식단표 게시물에서 이미지를 찾지 못했습니다.")
            return MenuPost(title, published_at, page_url, image_urls)
        return None

    def _recent_posts(self) -> list[dict[str, Any]]:
        url = f"https://m.blog.naver.com/api/blogs/{self.settings.blog_id}/post-list"
        try:
            response = self.session.get(
                url,
                params={"categoryNo": self.settings.category_no, "itemCount": 10},
                timeout=self.settings.request_timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise MenuSourceError("블로그 게시물 목록을 불러오지 못했습니다.") from exc

        items = payload.get("result", {}).get("items", [])
        if not isinstance(items, list):
            raise MenuSourceError("블로그 응답 형식이 예상과 다릅니다.")
        return items

    @staticmethod
    def _plain_title(raw_title: str) -> str:
        return BeautifulSoup(html.unescape(raw_title), "html.parser").get_text(" ", strip=True)

    @staticmethod
    def _published_at(item: dict[str, Any]) -> dt.datetime:
        try:
            timestamp = int(item["addDate"]) / 1000
            return dt.datetime.fromtimestamp(timestamp, KST)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise MenuSourceError("게시물의 작성일을 해석하지 못했습니다.") from exc

    def _content_images(self, page_url: str) -> tuple[str, ...]:
        try:
            response = self.session.get(
                page_url,
                headers={"Referer": f"https://m.blog.naver.com/{self.settings.blog_id}"},
                timeout=self.settings.request_timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise MenuSourceError("식단표 게시물을 불러오지 못했습니다.") from exc

        soup = BeautifulSoup(response.text, "html.parser")
        container = (
            soup.select_one(".se-main-container")
            or soup.select_one("#postViewArea")
            or soup
        )
        for image in container.select("img"):
            raw_url = next(
                (
                    image.get(attribute)
                    for attribute in ("data-lazy-src", "data-src", "data-original", "src")
                    if image.get(attribute)
                ),
                None,
            )
            if not raw_url or not self._is_content_image(raw_url):
                continue
            return self._quality_variants(raw_url)
        return ()

    @staticmethod
    def _is_content_image(url: str) -> bool:
        lowered = url.lower()
        supported_host = "postfiles.pstatic.net" in lowered or "blogfiles.pstatic.net" in lowered
        decorative = any(word in lowered for word in ("sticker", "profile", "emoticon", "icon"))
        return supported_host and not decorative

    @staticmethod
    def _quality_variants(url: str) -> tuple[str, ...]:
        base = url.split("?", 1)[0]
        return tuple(f"{base}?type=w{width}" for width in (3840, 2000, 966))
