from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_run import JobRun
from app.models.user import User
from app.schemas.job_schema import JobCreate, JobUpdate
from app.services.schedule_utils import compute_next_run


def create_job(db: Session, payload: JobCreate, current_user: User) -> Job:
    try:
        next_run_at = compute_next_run(payload.schedule_rule)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job = Job(
        task_name=payload.task_name,
        action_type=payload.action_type,
        action_payload=payload.action_payload,
        schedule_rule=payload.schedule_rule,
        timeout_seconds=payload.timeout_seconds,
        max_retry=payload.max_retry,
        enabled=payload.enabled,
        status="active" if payload.enabled else "disabled",
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

    if "schedule_rule" in data and data["schedule_rule"]:
        try:
            job.next_run_at = compute_next_run(data["schedule_rule"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    for key, value in data.items():
        setattr(job, key, value)

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
    job.status = "active" if enabled else "disabled"
    if enabled:
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
        action_payload=job.action_payload,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
