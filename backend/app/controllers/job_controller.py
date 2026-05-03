from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_run import JobRun
from app.models.user import User
from app.schemas.job_schema import JobCreate, JobUpdate
from app.services.schedule_utils import compute_next_run


ACTIVE_JOB_STATUSES = ("enabled", "active")


def _schedule_rule(schedule_type: str, cron_expression: str | None, interval_seconds: int | None) -> str:
    if schedule_type == "manual":
        return "manual"
    if schedule_type == "cron":
        return cron_expression or ""
    if schedule_type == "interval":
        return f"every:{interval_seconds}s"
    raise HTTPException(status_code=400, detail="Invalid schedule_type")


def _next_run_at(schedule_rule: str):
    if schedule_rule == "manual":
        return None
    try:
        return compute_next_run(schedule_rule)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _normalize_status(status: str | None, enabled: bool | None = None) -> str:
    if enabled is not None:
        return "enabled" if enabled else "disabled"
    if status == "active":
        return "enabled"
    return status or "enabled"


def create_job(db: Session, payload: JobCreate, current_user: User) -> Job:
    schedule_rule = _schedule_rule(payload.schedule_type, payload.cron_expression, payload.interval_seconds)
    status = _normalize_status(payload.status, payload.enabled)
    next_run_at = _next_run_at(schedule_rule) if status == "enabled" else None

    job = Job(
        task_name=payload.task_name,
        action_type=payload.action,
        action_payload=payload.action_payload,
        schedule_rule=schedule_rule,
        timeout_seconds=payload.timeout_seconds,
        max_retry=payload.retry_limit,
        enabled=status == "enabled",
        status=status,
        description=payload.description,
        user_id=current_user.id,
        next_run_at=next_run_at,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def list_jobs(db: Session, status: str | None = None, keyword: str | None = None) -> list[Job]:
    query = db.query(Job)
    if status == "enabled":
        query = query.filter(Job.enabled.is_(True))
    elif status == "disabled":
        query = query.filter(Job.enabled.is_(False))
    elif status == "active":
        query = query.filter(Job.status.in_(ACTIVE_JOB_STATUSES))
    elif status:
        query = query.filter(Job.status == status)
    if keyword:
        query = query.filter(Job.task_name.ilike(f"%{keyword}%"))
    return query.order_by(Job.created_at.desc()).all()


def get_job_or_404(db: Session, job_id: str) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def update_job(db: Session, job_id: str, payload: JobUpdate) -> Job:
    job = get_job_or_404(db, job_id)
    data = payload.model_dump(exclude_unset=True)

    if any(key in data for key in ("schedule_type", "cron_expression", "interval_seconds")):
        schedule_type = data.get("schedule_type", job.schedule_type)
        cron_expression = data.get("cron_expression", job.cron_expression)
        interval_seconds = data.get("interval_seconds", job.interval_seconds)
        data["schedule_rule"] = _schedule_rule(schedule_type, cron_expression, interval_seconds)

    if "action" in data:
        data["action_type"] = data.pop("action")
    if "retry_limit" in data:
        data["max_retry"] = data.pop("retry_limit")
    if "enabled" in data or "status" in data:
        status = _normalize_status(data.get("status", job.status), data.get("enabled"))
        data["status"] = status
        data["enabled"] = status == "enabled"

    ignored_fields = {"schedule_type", "cron_expression", "interval_seconds"}
    for key, value in data.items():
        if key in ignored_fields:
            continue
        setattr(job, key, value)

    if "schedule_rule" in data or "status" in data or "enabled" in data:
        job.next_run_at = _next_run_at(job.schedule_rule) if job.enabled and job.schedule_rule != "manual" else None

    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: str) -> dict:
    job = get_job_or_404(db, job_id)
    job.enabled = False
    job.status = "deleted"
    job.next_run_at = None
    db.commit()
    return {"message": "job deleted"}


def set_job_enabled(db: Session, job_id: str, enabled: bool) -> Job:
    job = get_job_or_404(db, job_id)
    job.enabled = enabled
    job.status = "enabled" if enabled else "disabled"
    if enabled and job.schedule_rule != "manual":
        job.next_run_at = compute_next_run(job.schedule_rule)
    else:
        job.next_run_at = None
    db.commit()
    db.refresh(job)
    return job


def trigger_job(db: Session, job_id: str, current_user: User | None = None, trigger_type: str = "manual") -> JobRun:
    job = get_job_or_404(db, job_id)

    run = JobRun(
        job_id=job.id,
        user_id=current_user.id if current_user else job.user_id,
        status="pending",
        trigger_type=trigger_type,
        triggered_by=trigger_type,
        action_payload=job.action_payload,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
