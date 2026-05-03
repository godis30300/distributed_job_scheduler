from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_log import JobLog
from app.models.job_run import JobRun
from app.models.user import User


TERMINAL_STATUSES = {"success", "failed", "timeout", "canceled"}
VALID_RUN_STATUSES = {"pending", "running", "success", "failed", "timeout", "canceled"}


def list_job_runs(
    db: Session,
    status: str | None = None,
    user_id: str | None = None,
    job_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[JobRun]:
    query = db.query(JobRun)
    if status:
        query = query.filter(JobRun.status == status)
    if user_id:
        query = query.filter(JobRun.user_id == user_id)
    if job_id:
        query = query.filter(JobRun.job_id == job_id)
    return query.order_by(JobRun.created_at.desc()).offset(offset).limit(limit).all()


def get_job_run(db: Session, run_id: str) -> JobRun:
    run = db.query(JobRun).filter(JobRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Job run not found")
    return run


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
        action_payload=job.action_payload,
    )
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
    if status not in VALID_RUN_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid job run status")

    run = get_job_run(db, run_id)
    now = datetime.now(timezone.utc)
    run.status = status

    if status == "running" and run.start_time is None:
        run.start_time = now
        run.heartbeat_at = now

    if status in TERMINAL_STATUSES:
        run.end_time = now
        run.heartbeat_at = now
        run.locked_by = None
        run.locked_until = None
        if run.start_time:
            run.duration_seconds = int((now - run.start_time).total_seconds())

    if stdout is not None:
        run.stdout = stdout
    if stderr is not None:
        run.stderr = stderr
    if error_message is not None:
        run.error_message = error_message

    db.commit()
    db.refresh(run)
    return run


def retry_job_run(db: Session, run_id: str, current_user: User | None = None) -> JobRun:
    run = get_job_run(db, run_id)
    if run.status not in ("failed", "timeout", "canceled"):
        raise HTTPException(status_code=400, detail="Only failed, timeout, or canceled runs can be retried")
    if run.job and run.retry_count >= run.job.max_retry:
        raise HTTPException(status_code=400, detail="Retry limit reached")

    new_run = JobRun(
        job_id=run.job_id,
        user_id=current_user.id if current_user else run.user_id,
        status="pending",
        trigger_type="retry",
        triggered_by="retry",
        retry_count=run.retry_count + 1,
        action_payload=run.job.action_payload if run.job else run.action_payload,
    )
    db.add(new_run)
    db.add(JobLog(job_run_id=run.id, log_level="info", stream="system", message=f"Retry created: {new_run.id}"))
    db.commit()
    db.refresh(new_run)
    return new_run


def retry_run(db: Session, run_id: str, current_user: User) -> JobRun:
    return retry_job_run(db, run_id, current_user)


def cancel_job_run(db: Session, run_id: str) -> JobRun:
    run = get_job_run(db, run_id)
    if run.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Only pending or running runs can be canceled")
    run.status = "canceled"
    now = datetime.now(timezone.utc)
    run.end_time = now
    run.locked_by = None
    run.locked_until = None
    if run.start_time:
        run.duration_seconds = int((now - run.start_time).total_seconds())
    db.add(JobLog(job_run_id=run.id, log_level="warning", stream="system", message="Run canceled by user"))
    db.commit()
    db.refresh(run)
    return run


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
    get_job_run(db, run_id)
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
    query = db.query(JobLog).join(JobRun, JobRun.id == JobLog.job_run_id).join(Job, Job.id == JobRun.job_id)
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
