from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.controllers.job_controller import trigger_job
from app.controllers.queue_controller import add_log
from app.models.job_log import JobLog
from app.models.job_run import JobRun
from app.models.user import User


def list_job_runs(db: Session, status: str | None = None, job_id: str | None = None) -> list[JobRun]:
    query = db.query(JobRun)
    if status:
        query = query.filter(JobRun.status == status)
    if job_id:
        query = query.filter(JobRun.job_id == job_id)
    return query.order_by(JobRun.created_at.desc()).limit(200).all()


def get_run_or_404(db: Session, run_id: str) -> JobRun:
    run = db.query(JobRun).filter(JobRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Job run not found")
    return run


def list_logs(db: Session, run_id: str) -> list[JobLog]:
    get_run_or_404(db, run_id)
    return db.query(JobLog).filter(JobLog.job_run_id == run_id).order_by(JobLog.created_at.asc()).all()


def retry_run(db: Session, run_id: str, current_user: User) -> JobRun:
    run = get_run_or_404(db, run_id)
    if run.status not in ("failed", "canceled"):
        raise HTTPException(status_code=400, detail="Only failed or canceled runs can be retried")

    new_run = JobRun(
        job_id=run.job_id,
        status="pending",
        triggered_by=current_user.id,
        trigger_type="retry",
        retry_count=run.retry_count + 1,
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    return new_run


def cancel_run(db: Session, run_id: str) -> JobRun:
    run = get_run_or_404(db, run_id)
    if run.status not in ("pending", "running", "waiting"):
        raise HTTPException(status_code=400, detail="Only pending/running/waiting runs can be canceled")
    run.status = "canceled"
    add_log(db, run.id, "WARN", "Run canceled by user")
    db.commit()
    db.refresh(run)
    return run
