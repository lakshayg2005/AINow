"""
Background pipeline jobs: ingest, compose, deliver.

Started from the admin dashboard or the scheduler. Each job
is a row in pipeline_jobs (so the dashboard can show progress
and history) and runs on a worker thread with its own event
loop and DB session, so embedding/LLM/SMTP work never blocks
the API.
"""

from __future__ import annotations

import asyncio
import traceback
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import NewsletterIssue, PipelineJob
from app.ingest.utils import utcnow


JOB_KINDS = ("ingest", "compose", "deliver")

# A job "running" longer than this died with its process.
STALE_AFTER = timedelta(hours=3)


class JobConflict(RuntimeError):
    pass


# ============================================================
# Bookkeeping
# ============================================================

def active_job(
    db: Session,
    kind: str,
    params: dict[str, Any] | None = None,
) -> PipelineJob | None:
    """
    The queued/running job of this kind, if any. Delivery jobs
    only conflict for the same issue.
    """

    jobs = db.scalars(
        select(PipelineJob).where(
            PipelineJob.kind == kind,
            PipelineJob.status.in_(("queued", "running")),
        )
    ).all()

    now = utcnow()

    for job in jobs:
        if now - (job.started_at or job.created_at) > STALE_AFTER:
            job.status = "failed"
            job.error = "Marked failed: exceeded time limit (process likely restarted)"
            job.finished_at = now
            db.commit()
            continue

        if kind == "deliver" and params is not None:
            if job.params.get("issue_id") != params.get("issue_id"):
                continue

        return job

    return None


def create_job(
    db: Session,
    kind: str,
    trigger: str = "manual",
    params: dict[str, Any] | None = None,
) -> PipelineJob:
    if kind not in JOB_KINDS:
        raise ValueError(f"Unknown job kind: {kind}")

    running = active_job(db, kind, params)

    if running is not None:
        raise JobConflict(
            f"{'An' if kind[0] in 'aeiou' else 'A'} {kind} job is already {running.status} (job #{running.id})"
        )

    job = PipelineJob(
        kind=kind,
        status="queued",
        trigger=trigger,
        params=params or {},
        result={},
        created_at=utcnow(),
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


# ============================================================
# Work
# ============================================================

async def _ingest(db: Session, params: dict) -> dict:
    from app.ingest.runner import run_ingestion
    from app.stories.service import update_stories

    stats = await run_ingestion(lookback_days=int(params.get("days", 7)))
    stories = await update_stories(db)

    return {"ingest": stats["totals"], "stories": stories}


async def _compose(db: Session, params: dict) -> dict:
    from app.compose.composer import compose_issue
    from app.compose.persist import save_issue_draft

    content = await compose_issue(db, window_days=int(params.get("days", 7)))
    issue = save_issue_draft(db, content)

    result = {
        "issue_id": issue.id,
        "headline": content.headline,
        "sources": len(content.sources),
        "models": content.stats.models,
    }

    if params.get("auto_publish"):
        from app.services.publishing import publish_issue

        result["stories_recorded"] = publish_issue(db, issue)
        deliver = create_job(db, "deliver", trigger="schedule", params={"issue_id": issue.id})
        result["deliver_job_id"] = deliver.id
        _run_sync(deliver.id)

    return result


def _deliver(db: Session, params: dict) -> dict:
    from app.services.delivery import deliver_issue

    return deliver_issue(
        db,
        int(params["issue_id"]),
        only_failed=bool(params.get("only_failed")),
    )


def _run_sync(
    job_id: int,
) -> None:
    """Execute a job on the current thread."""

    db = SessionLocal()

    try:
        job = db.get(PipelineJob, job_id)
        job.status = "running"
        job.started_at = utcnow()
        db.commit()

        params = dict(job.params or {})

        try:
            if job.kind == "ingest":
                result = asyncio.run(_ingest(db, params))
            elif job.kind == "compose":
                result = asyncio.run(_compose(db, params))
            else:
                result = _deliver(db, params)

            job = db.get(PipelineJob, job_id)
            job.status = "completed"
            job.result = _jsonable(result)

        except Exception as error:
            db.rollback()
            job = db.get(PipelineJob, job_id)
            job.status = "failed"
            job.error = (
                f"{type(error).__name__}: {error}\n\n"
                + traceback.format_exc()[-3000:]
            )
            print(f"[Jobs] #{job_id} {job.kind} failed: {error}")

        job.finished_at = utcnow()
        db.commit()

    finally:
        db.close()


def _jsonable(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


async def run_job(
    job_id: int,
) -> None:
    """Run a job off the event loop."""

    await asyncio.to_thread(_run_sync, job_id)


def start_job(
    kind: str,
    trigger: str = "manual",
    params: dict[str, Any] | None = None,
) -> PipelineJob:
    """
    Create a job and start it in the background of the
    running event loop. Raises JobConflict if one is active.
    """

    db = SessionLocal()

    try:
        job = create_job(db, kind, trigger, params)
        db.expunge(job)
    finally:
        db.close()

    asyncio.get_running_loop().create_task(run_job(job.id))

    return job


def latest_issue_created_at(
    db: Session,
):
    return db.scalar(
        select(NewsletterIssue.created_at)
        .order_by(NewsletterIssue.created_at.desc())
        .limit(1)
    )
