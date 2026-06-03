from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_dependency import JobDependency
from app.models.job_log import JobLog
from app.models.job_run import JobRun


def get_pending_jobs(db: Session, limit: int = 50) -> list[JobRun]:
    return (
        db.query(JobRun)
        .join(Job, Job.id == JobRun.job_id)
        .filter(JobRun.status == "pending")
        .filter(Job.enabled.is_(True))
        .filter(Job.status.in_(("enabled", "active")))
        .order_by(JobRun.created_at.asc())
        .limit(limit)
        .all()
    )


def lock_pending_job(db: Session, worker_name: str, lock_seconds: int = 3600) -> JobRun | None:
    run = (
        db.query(JobRun)
        .join(Job, Job.id == JobRun.job_id)
        .filter(JobRun.status == "pending")
        .filter(Job.enabled.is_(True))
        .filter(Job.status.in_(("enabled", "active")))
        .order_by(JobRun.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )

    if not run:
        return None

    now = datetime.now(timezone.utc)
    run.status = "running"
    run.worker_id = worker_name
    run.locked_by = worker_name
    run.locked_until = now + timedelta(seconds=lock_seconds)
    run.start_time = run.start_time or now
    run.heartbeat_at = now
    db.add(JobLog(job_run_id=run.id, log_level="info", stream="system", message=f"Locked by {worker_name}"))
    db.commit()
    db.refresh(run)
    return run


def dequeue_next_run(db: Session, worker_id: str) -> JobRun | None:
    return lock_pending_job(db, worker_id)


def release_expired_locks(db: Session) -> int:
    now = datetime.now(timezone.utc)
    expired_runs = (
        db.query(JobRun)
        .filter(JobRun.status == "running")
        .filter(JobRun.locked_until.isnot(None))
        .filter(JobRun.locked_until < now)
        .all()
    )

    for run in expired_runs:
        run.status = "pending"
        run.worker_id = None
        run.locked_by = None
        run.locked_until = None
        run.heartbeat_at = now
        db.add(JobLog(job_run_id=run.id, log_level="warning", stream="system", message="Expired lock released"))

    db.commit()
    return len(expired_runs)


def create_dependency(db: Session, job_id: str, depends_on_job_id: str) -> JobDependency:
    if job_id == depends_on_job_id:
        raise HTTPException(status_code=400, detail="Job cannot depend on itself")

    existing = (
        db.query(JobDependency)
        .filter(JobDependency.job_id == job_id)
        .filter(JobDependency.depends_on_job_id == depends_on_job_id)
        .first()
    )
    if existing:
        return existing

    dependency = JobDependency(job_id=job_id, depends_on_job_id=depends_on_job_id)
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


def check_dependency_finished(db: Session, job_id: str) -> bool:
    dependencies = db.query(JobDependency).filter(JobDependency.job_id == job_id).all()
    for dependency in dependencies:
        latest_run = (
            db.query(JobRun)
            .filter(JobRun.job_id == dependency.depends_on_job_id)
            .order_by(JobRun.created_at.desc())
            .first()
        )
        if not latest_run or latest_run.status != dependency.required_status:
            return False
    return True


def add_log(db: Session, run_id: str, level: str, message: str, stream: str = "system") -> JobLog:
    normalized_level = level.lower()
    if normalized_level == "warn":
        normalized_level = "warning"
    log = JobLog(job_run_id=run_id, log_level=normalized_level, stream=stream, message=message)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _set_duration(run: JobRun, end_time: datetime) -> None:
    if not run.start_time:
        return
    elapsed = max(0.001, (end_time - run.start_time).total_seconds())
    run.duration_ms = max(1, int(round(elapsed * 1000)))
    run.duration_seconds_decimal = round(run.duration_ms / 1000, 3)
    run.duration_seconds = max(1, int(ceil(elapsed)))


def finish_run(
    db: Session,
    run_id: str,
    status: str,
    error_message: str | None = None,
    stdout: str | None = None,
    stderr: str | None = None,
) -> JobRun | None:
    if status not in {"success", "failed", "timeout", "canceled"}:
        raise HTTPException(status_code=400, detail="Invalid terminal run status")

    run = db.query(JobRun).filter(JobRun.id == run_id).first()
    if not run:
        return None

    now = datetime.now(timezone.utc)
    run.status = status
    run.end_time = now
    run.heartbeat_at = now
    run.locked_by = None
    run.locked_until = None
    run.error_message = error_message
    if error_message:
        db.add(JobLog(job_run_id=run.id, log_level="error", stream="system", message=error_message))
    if stdout is not None:
        run.stdout = stdout
        if stdout:
            db.add(JobLog(job_run_id=run.id, log_level="info", stream="stdout", message=stdout))
    if stderr is not None:
        run.stderr = stderr
        if stderr:
            db.add(JobLog(job_run_id=run.id, log_level="error", stream="stderr", message=stderr))
    _set_duration(run, now)

    level = "info" if status == "success" else "error"
    db.add(JobLog(job_run_id=run.id, log_level=level, stream="system", message=f"Run finished: {status}"))
    db.commit()
    db.refresh(run)
    return run


def heartbeat(db: Session, run_id: str) -> JobRun | None:
    run = db.query(JobRun).filter(JobRun.id == run_id).first()
    if not run:
        return None
    run.heartbeat_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
