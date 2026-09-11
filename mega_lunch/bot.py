from __future__ import annotations

import asyncio
import datetime as dt
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .cache import MenuImageError
from .calendar import WEEKDAY_NAMES, WeekKey, is_serving_day, relative_day, relative_week
from .schedule import (
    GuildScheduleStore,
    HungerPhase,
    format_remaining_minutes,
    hunger_status,
    parse_clock_time,
)
from .models import CachedMenu
from .prefetch import PREFETCH_TIME, scheduled_prefetch_week
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
        self.schedules = GuildScheduleStore(settings.cache_dir / "guild-schedules.json")

    async def setup_hook(self) -> None:
        register_commands(self)
        synced = await self.tree.sync()
        log.info("슬래시 명령어 %d개 동기화 완료", len(synced))
        self.prefetch_next_week.start()

    async def close(self) -> None:
        self.prefetch_next_week.cancel()
        await super().close()

    async def on_ready(self) -> None:
        log.info("로그인 완료: %s", self.user)
        await self.change_presence(activity=discord.Game(name="/오늘점심"))

    @tasks.loop(time=PREFETCH_TIME)
    async def prefetch_next_week(self) -> None:
        week = scheduled_prefetch_week(_today())
        if week is None:
            return

        try:
            await self.menu_service.get(week)
            log.info("다음 주 식단표 사전 캐시 완료: %s", week)
        except (MenuNotPublished, MenuSourceError, MenuImageError) as exc:
            log.warning("다음 주 식단표 사전 캐시 실패: %s", exc)
        except Exception:
            log.exception("다음 주 식단표 사전 캐시 중 예상하지 못한 오류 발생")

    @prefetch_next_week.before_loop
    async def before_prefetch_next_week(self) -> None:
        await self.wait_until_ready()


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

    @bot.tree.command(name="배고파", description="점심 또는 퇴근까지 남은 시간을 알려줍니다.")
    async def hungry(interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        if guild_id is None:
            await interaction.response.send_message(
                "⚠️ `/배고파`는 서버에서만 사용할 수 있어요.",
                ephemeral=True,
            )
            return

        schedule = await asyncio.to_thread(bot.schedules.get, guild_id)
        status = hunger_status(_now(), schedule)
        if status.phase is HungerPhase.WEEKEND:
            message = "🌿 오늘은 쉬는 날이에요!"
        elif status.phase is HungerPhase.BEFORE_LUNCH:
            remaining = format_remaining_minutes(status.remaining_minutes or 1)
            message = (
                f"🍚 점심시간 **{schedule.lunch_time.strftime('%H:%M')}**까지 "
                f"**{remaining}** 남았어요!"
            )
        elif status.phase is HungerPhase.LUNCH:
            message = "🍱 지금은 점심시간이에요! 맛있게 드세요."
        elif status.phase is HungerPhase.WORK_END_UNSET:
            message = "⚠️ 이 서버의 퇴근시간이 아직 설정되지 않았어요."
        elif status.phase is HungerPhase.BEFORE_WORK_END:
            remaining = format_remaining_minutes(status.remaining_minutes or 1)
            message = (
                f"🏃 퇴근시간 **{schedule.work_end_time.strftime('%H:%M')}**까지 "
                f"**{remaining}** 남았어요!"
            )
        else:
            message = "🏠 퇴근시간이 지났어요. 집에 가서 밥 먹어요!"

        await interaction.response.send_message(message)

    @bot.tree.command(name="점심시간설정", description="내 점심시간을 설정합니다.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.rename(lunch_time="시간")
    @app_commands.describe(lunch_time="24시간 형식으로 입력해 주세요. 예: 12:50")
    async def set_lunch_time(
        interaction: discord.Interaction,
        lunch_time: str,
    ) -> None:
        guild_id = await _editable_schedule_guild_id(interaction)
        if guild_id is None:
            return
        try:
            parsed = parse_clock_time(lunch_time)
        except ValueError:
            await interaction.response.send_message(
                "⚠️ 점심시간은 `HH:MM` 형식으로 입력해 주세요. 예: `12:50`",
                ephemeral=True,
            )
            return

        try:
            await asyncio.to_thread(
                bot.schedules.set_lunch_time,
                guild_id,
                parsed,
            )
        except OSError:
            log.exception("점심시간 설정 저장 실패")
            await interaction.response.send_message(
                "❌ 점심시간 설정을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ 이 서버의 점심시간을 **{parsed.strftime('%H:%M')}**으로 설정했어요.",
            ephemeral=True,
        )

    @bot.tree.command(name="퇴근시간설정", description="내 퇴근시간을 설정합니다.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.rename(work_end_time="시간")
    @app_commands.describe(work_end_time="24시간 형식으로 입력해 주세요. 예: 17:50")
    async def set_work_end_time(
        interaction: discord.Interaction,
        work_end_time: str,
    ) -> None:
        guild_id = await _editable_schedule_guild_id(interaction)
        if guild_id is None:
            return
        try:
            parsed = parse_clock_time(work_end_time)
        except ValueError:
            await interaction.response.send_message(
                "⚠️ 퇴근시간은 `HH:MM` 형식으로 입력해 주세요. 예: `17:50`",
                ephemeral=True,
            )
            return

        try:
            await asyncio.to_thread(
                bot.schedules.set_work_end_time,
                guild_id,
                parsed,
            )
        except OSError:
            log.exception("퇴근시간 설정 저장 실패")
            await interaction.response.send_message(
                "❌ 퇴근시간 설정을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ 이 서버의 퇴근시간을 **{parsed.strftime('%H:%M')}**으로 설정했어요.",
            ephemeral=True,
        )


def _now() -> dt.datetime:
    return dt.datetime.now(KST)


def _today() -> dt.date:
    return _now().date()


async def _editable_schedule_guild_id(
    interaction: discord.Interaction,
) -> int | None:
    if interaction.guild_id is None:
        await interaction.response.send_message(
            "⚠️ 시간 설정은 서버에서만 사용할 수 있어요.",
            ephemeral=True,
        )
        return None
    if not interaction.permissions.manage_guild:
        await interaction.response.send_message(
            "⚠️ 시간 설정에는 `서버 관리` 권한이 필요해요.",
            ephemeral=True,
        )
        return None
    return interaction.guild_id


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
