from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.infrastructure.repositories.job_repository import JobRepository
from app.infrastructure.repositories.job_run_repository import JobRunRepository


def dashboard_summary(db: Session) -> dict:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    job_repo = JobRepository(db)
    run_repo = JobRunRepository(db)

    total_jobs = job_repo.count()
    enabled_jobs = job_repo.count_enabled()

    pending_runs = run_repo.count(status="pending")
    running_runs = run_repo.count(status="running")
    
    success_today = run_repo.count_by_status_since("success", today)
    failed_today = run_repo.count_by_status_since(["failed", "timeout"], today)
    total_runs_today = run_repo.count_since(today)

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
