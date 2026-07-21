from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent.parent
KST = ZoneInfo("Asia/Seoul")


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    discord_token: str
    blog_id: str
    category_no: str
    title_keyword: str
    cache_dir: Path
    request_timeout: float
    max_download_bytes: int
    max_image_pixels: int
    day_image_width: int
    crop_top: float
    crop_height: float
    crop_left: float
    crop_width: float

    @classmethod
    def load(cls) -> "Settings":
        _load_env_file(BASE_DIR / ".env")

        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            token_file = BASE_DIR / "token.txt"
            if token_file.exists():
                token = token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise RuntimeError("DISCORD_TOKEN 환경변수 또는 .env 설정이 필요합니다.")

        return cls(
            discord_token=token,
            blog_id=os.getenv("MENU_BLOG_ID", "megafs01"),
            category_no=os.getenv("MENU_CATEGORY_NO", "41"),
            title_keyword=os.getenv("MENU_TITLE_KEYWORD", "[메가스터디 구내식당]"),
            cache_dir=BASE_DIR / os.getenv("MENU_CACHE_DIR", "cache"),
            request_timeout=_float_env("MENU_REQUEST_TIMEOUT", 10.0),
            max_download_bytes=int(9.5 * 1024 * 1024),
            max_image_pixels=24_000_000,
            day_image_width=800,
            crop_top=_float_env("MENU_CROP_TOP", 0.232),
            crop_height=_float_env("MENU_CROP_HEIGHT", 0.25),
            crop_left=_float_env("MENU_CROP_LEFT", 0.169),
            crop_width=_float_env("MENU_CROP_WIDTH", 0.81),
        )
