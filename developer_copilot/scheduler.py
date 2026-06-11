from __future__ import annotations

from typing import Any

from developer_copilot.briefings import create_daily_briefing
from developer_copilot.config import Settings


def start_scheduler(settings: Settings) -> Any | None:
    if not settings.scheduler_enabled:
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        return None

    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(
        lambda: create_daily_briefing(settings, send_whatsapp=True),
        CronTrigger(
            hour=settings.scheduler_hour,
            minute=settings.scheduler_minute,
            timezone=settings.scheduler_timezone,
        ),
        id="daily-developer-copilot-briefing",
        name="Daily Developer Co-pilot WhatsApp briefing",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    return scheduler


def stop_scheduler(scheduler: Any | None) -> None:
    if scheduler is not None:
        scheduler.shutdown(wait=False)

