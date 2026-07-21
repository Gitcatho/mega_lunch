from __future__ import annotations

import datetime as dt
import logging

import discord
from discord import app_commands
from discord.ext import commands

from .cache import MenuImageError
from .calendar import WEEKDAY_NAMES, WeekKey, is_serving_day, relative_day, relative_week
from .models import CachedMenu
from .service import MenuNotPublished, MenuService
from .settings import KST, Settings
from .source import MenuSourceError


log = logging.getLogger(__name__)

NEXT_WEEK_NOT_PUBLISHED_MESSAGE = (
    "🍚 다음 주 식단표가 아직 올라오지 않았어요.\n"
    "보통 **금요일**에 게시되니 조금 뒤에 다시 확인해 주세요!"
)


class MegaLunchBot(commands.Bot):
    def __init__(self, settings: Settings):
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
            max_messages=None,
            chunk_guilds_at_startup=False,
            member_cache_flags=discord.MemberCacheFlags.none(),
        )
        self.settings = settings
        self.menu_service = MenuService(settings)

    async def setup_hook(self) -> None:
        register_commands(self)
        synced = await self.tree.sync()
        log.info("슬래시 명령어 %d개 동기화 완료", len(synced))

    async def on_ready(self) -> None:
        log.info("로그인 완료: %s", self.user)
        await self.change_presence(activity=discord.Game(name="/오늘점심"))


def register_commands(bot: MegaLunchBot) -> None:
    @bot.tree.command(name="오늘점심", description="오늘의 구내식당 점심 메뉴를 보여줍니다.")
    async def today_lunch(interaction: discord.Interaction) -> None:
        await _send_day(interaction, bot.menu_service, relative_day(_today(), 0), "오늘")

    @bot.tree.command(name="내일점심", description="내일의 구내식당 점심 메뉴를 보여줍니다.")
    async def tomorrow_lunch(interaction: discord.Interaction) -> None:
        await _send_day(interaction, bot.menu_service, relative_day(_today(), 1), "내일")

    @bot.tree.command(name="이번주", description="이번 주 전체 식단표를 보여줍니다.")
    async def this_week(interaction: discord.Interaction) -> None:
        await _send_week(interaction, bot.menu_service, relative_week(_today()), "이번 주")

    @bot.tree.command(name="다음주", description="다음 주 전체 식단표를 보여줍니다.")
    async def next_week(interaction: discord.Interaction) -> None:
        await _send_week(
            interaction,
            bot.menu_service,
            relative_week(_today(), 1),
            "다음 주",
            not_published_message=NEXT_WEEK_NOT_PUBLISHED_MESSAGE,
        )


def _today() -> dt.date:
    return dt.datetime.now(KST).date()


async def _send_day(
    interaction: discord.Interaction,
    service: MenuService,
    target_date: dt.date,
    relative_name: str,
) -> None:
    if not is_serving_day(target_date):
        await interaction.response.send_message(
            f"🛌 {relative_name}은 {WEEKDAY_NAMES[target_date.weekday()] if target_date.weekday() < 5 else '주말'}이라 "
            "구내식당 점심 메뉴가 없습니다."
        )
        return

    await interaction.response.defer(thinking=True)
    try:
        menu = await service.get(WeekKey.from_date(target_date))
        image_path = menu.day_images[target_date.weekday()]
        filename = f"mega-lunch-{target_date.isoformat()}.png"
        embed = discord.Embed(
            title=f"🍚 {relative_name} 점심 · {WEEKDAY_NAMES[target_date.weekday()]}",
            description=f"**{target_date.isoformat()}** 메가스터디 구내식당",
            color=0x2E8B57,
            url=menu.page_url,
        )
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text=f"{menu.week.week}주차 · 원본 이미지를 보려면 /이번주 또는 /다음주")
        await interaction.followup.send(
            embed=embed,
            file=discord.File(image_path, filename=filename),
        )
    except (MenuNotPublished, MenuSourceError, MenuImageError) as exc:
        await _send_known_error(interaction, exc)
    except Exception:
        log.exception("요일 메뉴 전송 실패")
        await interaction.followup.send("❌ 메뉴를 처리하는 중 예상하지 못한 오류가 발생했습니다.")


async def _send_week(
    interaction: discord.Interaction,
    service: MenuService,
    week: WeekKey,
    label: str,
    not_published_message: str | None = None,
) -> None:
    await interaction.response.defer(thinking=True)
    try:
        menu = await service.get(week)
        await _send_full_image(interaction, menu, label)
    except MenuNotPublished as exc:
        await interaction.followup.send(not_published_message or f"⚠️ {exc}")
    except (MenuSourceError, MenuImageError) as exc:
        await _send_known_error(interaction, exc)
    except Exception:
        log.exception("주간 메뉴 전송 실패")
        await interaction.followup.send("❌ 메뉴를 처리하는 중 예상하지 못한 오류가 발생했습니다.")


async def _send_full_image(
    interaction: discord.Interaction,
    menu: CachedMenu,
    label: str,
) -> None:
    filename = f"mega-lunch-{menu.week}{menu.full_image.suffix}"
    embed = discord.Embed(
        title=f"📅 {label} 식단표",
        description=f"**{menu.week.week}주차** · 게시일 {menu.published_at.date().isoformat()}",
        color=0x3078C6,
        url=menu.page_url,
    )
    embed.set_image(url=f"attachment://{filename}")
    embed.add_field(name="원본 게시물", value=f"[네이버 블로그에서 보기]({menu.page_url})")
    await interaction.followup.send(
        embed=embed,
        file=discord.File(menu.full_image, filename=filename),
    )


async def _send_known_error(interaction: discord.Interaction, error: Exception) -> None:
    await interaction.followup.send(f"⚠️ {error}")


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    settings = Settings.load()
    MegaLunchBot(settings).run(settings.discord_token, log_handler=None)
