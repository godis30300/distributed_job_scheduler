from sqlalchemy.orm import Session
from app.domain.entities.job_log import JobLog
from app.domain.entities.job_run import JobRun
from app.application.services.job_run_service import JobRunService
from app.infrastructure.repositories.job_run_repository import JobRunRepository
from app.domain.exceptions import EntityNotFoundError


def get_pending_jobs(db: Session, limit: int = 50) -> list[JobRun]:
    repo = JobRunRepository(db)
    # Correct the logic to return a list of pending jobs
    return repo.db.query(JobRun).filter(JobRun.status == "pending").limit(limit).all()


def lock_pending_job(db: Session, worker_name: str, lock_seconds: int = 3600) -> JobRun | None:
    service = JobRunService(db)
    return service.dequeue_next_run(worker_name, lock_seconds)


def dequeue_next_run(db: Session, worker_id: str) -> JobRun | None:
    return lock_pending_job(db, worker_id)


def release_expired_locks(db: Session) -> int:
    service = JobRunService(db)
    return service.release_expired_locks()


def add_log(db: Session, run_id: str, level: str, message: str, stream: str = "system") -> JobLog:
    normalized_level = level.lower()
    if normalized_level == "warn":
        normalized_level = "warning"
    log = JobLog(job_run_id=run_id, log_level=normalized_level, stream=stream, message=message)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def finish_run(
    db: Session,
    run_id: str,
    status: str,
    error_message: str | None = None,
    stdout: str | None = None,
    stderr: str | None = None,
) -> JobRun | None:
    service = JobRunService(db)
    try:
        return service.update_status(run_id, status, stdout, stderr, error_message)
    except EntityNotFoundError:
        return None


def heartbeat(db: Session, run_id: str) -> JobRun | None:
    service = JobRunService(db)
    try:
        return service.heartbeat(run_id)
    except EntityNotFoundError:
        return None
