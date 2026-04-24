from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_run import JobRun


def dashboard_summary(db: Session) -> dict:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    enabled_jobs = db.query(func.count(Job.id)).filter(Job.enabled.is_(True)).scalar() or 0

    pending_runs = db.query(func.count(JobRun.id)).filter(JobRun.status == "pending").scalar() or 0
    running_runs = db.query(func.count(JobRun.id)).filter(JobRun.status == "running").scalar() or 0
    success_today = (
        db.query(func.count(JobRun.id))
        .filter(JobRun.status == "success", JobRun.created_at >= today)
        .scalar()
        or 0
    )
    failed_today = (
        db.query(func.count(JobRun.id))
        .filter(JobRun.status == "failed", JobRun.created_at >= today)
        .scalar()
        or 0
    )
    total_runs_today = (
        db.query(func.count(JobRun.id)).filter(JobRun.created_at >= today).scalar() or 0
    )

    return {
        "total_jobs": total_jobs,
        "enabled_jobs": enabled_jobs,
        "pending_runs": pending_runs,
        "running_runs": running_runs,
        "success_today": success_today,
        "failed_today": failed_today,
        "total_runs_today": total_runs_today,
        "worker_count_hint": 1,
    }
