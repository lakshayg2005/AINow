"""
Built-in scheduler (enable with SCHEDULER_ENABLED=true).

    - ingest every INGEST_EVERY_HOURS
    - compose a draft once a week at COMPOSE_WEEKDAY /
      COMPOSE_HOUR_UTC
    - publish + deliver automatically only if AUTO_PUBLISH=true;
      otherwise the draft waits for review in /admin

Runs inside the API process: start a single worker when it is
enabled, or two workers would both schedule jobs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import IngestRun, PipelineJob
from app.ingest.utils import utcnow
from app.jobs import JobConflict, latest_issue_created_at, start_job


TICK_SECONDS = 60


def last_compose_slot(
    now: datetime,
    weekday: int,
    hour: int,
) -> datetime:
    """Most recent weekday/hour boundary at or before `now`."""

    slot = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    slot -= timedelta(days=(now.weekday() - weekday) % 7)

    if slot > now:
        slot -= timedelta(days=7)

    return slot


def ingest_due(
    now: datetime,
    last_run: datetime | None,
    every_hours: float,
) -> bool:
    return last_run is None or now - last_run >= timedelta(hours=every_hours)


def compose_due(
    now: datetime,
    last_compose: datetime | None,
    weekday: int,
    hour: int,
) -> bool:
    slot = last_compose_slot(now, weekday, hour)
    return last_compose is None or last_compose < slot


def _latest(db, column) -> datetime | None:
    return db.scalar(select(func.max(column)))


def tick(
    now: datetime | None = None,
) -> list[str]:
    """Start whatever is due. Returns the kinds started."""

    now = now or utcnow()
    started: list[str] = []
    db = SessionLocal()

    try:
        # CLI runs count too, so a manual ingest resets the clock.
        last_ingest = max(
            filter(
                None,
                [
                    _latest(db, IngestRun.started_at),
                    db.scalar(
                        select(func.max(PipelineJob.created_at)).where(
                            PipelineJob.kind == "ingest"
                        )
                    ),
                ],
            ),
            default=None,
        )

        last_compose = max(
            filter(
                None,
                [
                    latest_issue_created_at(db),
                    db.scalar(
                        select(func.max(PipelineJob.created_at)).where(
                            PipelineJob.kind == "compose"
                        )
                    ),
                ],
            ),
            default=None,
        )
    finally:
        db.close()

    if ingest_due(now, last_ingest, settings.ingest_every_hours):
        try:
            start_job("ingest", trigger="schedule")
            started.append("ingest")
        except JobConflict:
            pass

    if compose_due(now, last_compose, settings.compose_weekday, settings.compose_hour_utc):
        try:
            start_job(
                "compose",
                trigger="schedule",
                params={"auto_publish": settings.auto_publish},
            )
            started.append("compose")
        except JobConflict:
            pass

    return started


async def scheduler_loop() -> None:
    print(
        "[Scheduler] Enabled: ingest every "
        f"{settings.ingest_every_hours}h, compose weekday "
        f"{settings.compose_weekday} at {settings.compose_hour_utc}:00 UTC, "
        f"auto-publish={'on' if settings.auto_publish else 'off'}"
    )

    while True:
        try:
            started = tick()

            if started:
                print(f"[Scheduler] Started: {', '.join(started)}")

        except Exception as error:
            print(f"[Scheduler] tick failed: {type(error).__name__}: {error}")

        await asyncio.sleep(TICK_SECONDS)
