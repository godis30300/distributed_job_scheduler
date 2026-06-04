from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.domain.entities.job import Job
from app.domain.entities.job_log import JobLog
from app.domain.entities.job_run import JobRun
from app.domain.entities.user import User
from app.application.services.job_run_service import JobRunService
from app.domain.exceptions import EntityNotFoundError, BusinessRuleViolationError
from app.infrastructure.repositories.job_run_repository import JobRunRepository


def list_job_runs(
    db: Session,
    status: str | None = None,
    user_id: str | None = None,
    job_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[JobRun]:
    repo = JobRunRepository(db)
    
    # We can use the generic list method
    filters = {}
    if status: filters["status"] = status
    if user_id: filters["user_id"] = user_id
    if job_id: filters["job_id"] = job_id
    
    return repo.list(skip=offset, limit=limit, **filters)


def get_job_run(db: Session, run_id: str) -> JobRun:
    service = JobRunService(db)
    try:
        return service.get_run(run_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


def get_run_or_404(db: Session, run_id: str) -> JobRun:
    return get_job_run(db, run_id)


def create_job_run(
    db: Session,
    job: Job,
    triggered_by: str = "scheduler",
    start_as_pending: bool = True,
    user_id: str | None = None,
    retry_count: int = 0,
) -> JobRun:
    run = JobRun(
        job_id=job.id,
        user_id=user_id or job.user_id,
        status="pending" if start_as_pending else "running",
        trigger_type=triggered_by,
        triggered_by=triggered_by,
        retry_count=retry_count,
        action_type=job.action_type,
        action_payload=job.action_payload,
        timeout_seconds=job.timeout_seconds,
    )
    if not start_as_pending:
        run.start()
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def update_job_run_status(
    db: Session,
    run_id: str,
    status: str,
    stdout: str | None = None,
    stderr: str | None = None,
    error_message: str | None = None,
) -> JobRun:
    service = JobRunService(db)
    try:
        return service.update_status(run_id, status, stdout, stderr, error_message)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=400, detail=str(e))


def retry_job_run(db: Session, run_id: str, current_user: User | None = None) -> JobRun:
    service = JobRunService(db)
    try:
        return service.retry_run(run_id, current_user.id if current_user else None)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessRuleViolationError as e:
        raise HTTPException(status_code=400, detail=str(e))


def retry_run(db: Session, run_id: str, current_user: User) -> JobRun:
    return retry_job_run(db, run_id, current_user)


def cancel_job_run(db: Session, run_id: str) -> JobRun:
    service = JobRunService(db)
    try:
        return service.update_status(run_id, "canceled")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def cancel_run(db: Session, run_id: str) -> JobRun:
    return cancel_job_run(db, run_id)


def save_job_log(
    db: Session,
    run_id: str,
    log_level: str,
    message: str,
    stream: str = "system",
) -> JobLog:
    get_job_run(db, run_id)
    normalized_level = log_level.lower()
    if normalized_level == "warn":
        normalized_level = "warning"
    log = JobLog(job_run_id=run_id, log_level=normalized_level, stream=stream, message=message)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_job_run_logs(db: Session, run_id: str) -> list[JobLog]:
    return db.query(JobLog).filter(JobLog.job_run_id == run_id).order_by(JobLog.created_at.asc()).all()


def list_logs(db: Session, run_id: str) -> list[JobLog]:
    return get_job_run_logs(db, run_id)


def search_job_logs(
    db: Session,
    task_name: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
    log_level: str | None = None,
    start_time_from: datetime | None = None,
    start_time_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[JobLog]:
    query = (
        db.query(JobLog)
        .join(JobRun, JobRun.id == JobLog.job_run_id)
        .join(Job, Job.id == JobRun.job_id)
    )

    if task_name:
        query = query.filter(Job.task_name == task_name)
    if status:
        query = query.filter(JobRun.status == status)
    if user_id:
        query = query.filter(JobRun.user_id == user_id)
    if log_level:
        query = query.filter(JobLog.log_level == log_level.lower())
    if start_time_from:
        query = query.filter(JobRun.start_time >= start_time_from)
    if start_time_to:
        query = query.filter(JobRun.start_time <= start_time_to)

    return query.order_by(JobLog.created_at.desc()).offset(offset).limit(limit).all()
