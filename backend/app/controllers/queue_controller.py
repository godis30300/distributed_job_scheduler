from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.job_run import JobRun
from app.models.job_log import JobLog
from app.services.schedule_utils import utcnow


def dequeue_next_run(db: Session, worker_id: str) -> JobRun | None:
    run = (
        db.query(JobRun)
        .filter(JobRun.status == "pending")
        .order_by(JobRun.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )

    if not run:
        return None

    now = utcnow()
    run.status = "running"
    run.worker_id = worker_id
    run.start_time = now
    run.heartbeat_at = now
    db.add(JobLog(job_run_id=run.id, log_level="INFO", message=f"Dequeued by {worker_id}"))
    db.commit()
    db.refresh(run)
    return run


def add_log(db: Session, run_id: str, level: str, message: str) -> JobLog:
    log = JobLog(job_run_id=run_id, log_level=level, message=message)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def finish_run(db: Session, run_id: str, status: str, error_message: str | None = None) -> JobRun | None:
    run = db.query(JobRun).filter(JobRun.id == run_id).first()
    if not run:
        return None

    now = utcnow()
    run.status = status
    run.end_time = now
    run.heartbeat_at = now
    run.error_message = error_message
    if run.start_time:
        run.duration_seconds = int((now - run.start_time).total_seconds())

    db.add(JobLog(job_run_id=run.id, log_level="INFO" if status == "success" else "ERROR", message=f"Run finished: {status}"))
    db.commit()
    db.refresh(run)
    return run


def heartbeat(db: Session, run_id: str) -> JobRun | None:
    run = db.query(JobRun).filter(JobRun.id == run_id).first()
    if not run:
        return None
    run.heartbeat_at = utcnow()
    db.commit()
    db.refresh(run)
    return run
