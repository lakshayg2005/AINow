from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.compose.persist import load_issue_content
from app.core.config import settings
from app.core.dependencies import get_current_admin
from app.db.database import get_db
from app.db.models import (
    IngestRun,
    NewsletterDelivery,
    NewsletterIssue,
    NewsletterSection,
    PipelineJob,
    Story,
    Subscription,
    User,
)
from app.ingest.utils import utcnow
from app.jobs import JobConflict, start_job
from app.services.delivery import delivery_stats, send_test_email
from app.services.publishing import PublishError, publish_issue


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_admin)],
)


class TestSendRequest(BaseModel):
    email: EmailStr | None = None


class ComposeRequest(BaseModel):
    days: int = 7


def _job(job: PipelineJob) -> dict:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "trigger": job.trigger,
        "params": job.params,
        "result": job.result,
        "error": (job.error or "").split("\n\n")[0] or None,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


def _get_issue(db: Session, issue_id: int) -> NewsletterIssue:
    issue = db.get(NewsletterIssue, issue_id)

    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Newsletter not found")

    return issue


def _start(kind: str, params: dict | None = None) -> dict:
    try:
        return _job(start_job(kind, trigger="manual", params=params))
    except JobConflict as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error))


# ---------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------

@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    last_run = db.scalar(
        select(IngestRun).order_by(IngestRun.started_at.desc()).limit(1)
    )

    week_ago = utcnow() - timedelta(days=7)

    subscribers = db.scalar(
        select(func.count())
        .select_from(Subscription)
        .join(User, User.id == Subscription.user_id)
        .where(Subscription.status == "active", User.is_email_verified.is_(True))
    )

    jobs = db.scalars(
        select(PipelineJob).order_by(PipelineJob.created_at.desc()).limit(10)
    ).all()

    return {
        "subscribers": subscribers or 0,
        "stories_this_week": db.scalar(
            select(func.count()).select_from(Story).where(Story.last_seen_at >= week_ago)
        )
        or 0,
        "last_ingest": (
            {
                "started_at": last_run.started_at,
                "finished_at": last_run.finished_at,
                "status": last_run.status,
                "totals": (last_run.stats or {}).get("totals", {}),
                "errors": len(last_run.errors or []),
            }
            if last_run
            else None
        ),
        "scheduler": {
            "enabled": settings.scheduler_enabled,
            "ingest_every_hours": settings.ingest_every_hours,
            "compose_weekday": settings.compose_weekday,
            "compose_hour_utc": settings.compose_hour_utc,
            "auto_publish": settings.auto_publish,
        },
        "jobs": [_job(job) for job in jobs],
    }


# ---------------------------------------------------------
# JOBS
# ---------------------------------------------------------

@router.post("/jobs/ingest", status_code=status.HTTP_202_ACCEPTED)
async def run_ingest():
    return _start("ingest")


@router.post("/jobs/compose", status_code=status.HTTP_202_ACCEPTED)
async def run_compose(request: ComposeRequest | None = None):
    return _start("compose", {"days": (request or ComposeRequest()).days})


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(PipelineJob, job_id)

    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    return _job(job)


# ---------------------------------------------------------
# ISSUES
# ---------------------------------------------------------

@router.get("/issues")
def list_issues(db: Session = Depends(get_db)):
    issues = db.scalars(
        select(NewsletterIssue).order_by(NewsletterIssue.created_at.desc()).limit(50)
    ).all()

    counts: dict[int, dict[str, int]] = {}

    for issue_id, delivery_status, count in db.execute(
        select(
            NewsletterDelivery.newsletter_issue_id,
            NewsletterDelivery.status,
            func.count(),
        ).group_by(
            NewsletterDelivery.newsletter_issue_id,
            NewsletterDelivery.status,
        )
    ):
        counts.setdefault(issue_id, {})[delivery_status] = count

    rows = []

    for issue in issues:
        content = load_issue_content(issue)

        rows.append(
            {
                "id": issue.id,
                "title": issue.title,
                "headline": content.headline if content else None,
                "status": issue.status,
                "format": 2 if content else 1,
                "created_at": issue.created_at,
                "published_at": issue.published_at,
                "stories": len(content.story_ids()) if content else None,
                "sources": len(content.sources) if content else None,
                "models": content.stats.models if content else [],
                "deliveries": counts.get(issue.id, {}),
            }
        )

    return rows


@router.post("/issues/{issue_id}/test-send")
async def test_send(
    issue_id: int,
    request: TestSendRequest | None = None,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    import asyncio

    issue = _get_issue(db, issue_id)

    try:
        target = await asyncio.to_thread(
            send_test_email,
            issue,
            admin,
            (request or TestSendRequest()).email,
        )
    except Exception as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Sending failed: {type(error).__name__}: {error}",
        )

    return {"message": f"Test email sent to {target}"}


@router.post("/issues/{issue_id}/publish", status_code=status.HTTP_202_ACCEPTED)
async def publish(issue_id: int, db: Session = Depends(get_db)):
    issue = _get_issue(db, issue_id)

    try:
        recorded = publish_issue(db, issue)
    except PublishError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error))

    return {
        "message": "Published; delivery started",
        "stories_recorded": recorded,
        "job": _start("deliver", {"issue_id": issue.id}),
    }


@router.post("/issues/{issue_id}/retry-failed", status_code=status.HTTP_202_ACCEPTED)
async def retry_failed(issue_id: int, db: Session = Depends(get_db)):
    issue = _get_issue(db, issue_id)

    if issue.status != "published":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Issue is not published")

    return _start("deliver", {"issue_id": issue.id, "only_failed": True})


@router.get("/issues/{issue_id}/deliveries")
def deliveries(issue_id: int, db: Session = Depends(get_db)):
    _get_issue(db, issue_id)
    return delivery_stats(db, issue_id)


@router.delete("/issues/{issue_id}")
def delete_draft(issue_id: int, db: Session = Depends(get_db)):
    issue = _get_issue(db, issue_id)

    if issue.status != "draft":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only drafts can be deleted; published issues are part of the archive",
        )

    db.query(NewsletterSection).filter(
        NewsletterSection.newsletter_issue_id == issue.id
    ).delete()
    db.delete(issue)
    db.commit()

    return {"message": f"Draft {issue_id} deleted"}
