from sqlalchemy.orm import Session
from app.application.services.job_service import JobService
from app.services.schedule_utils import utcnow


def scan_due_jobs(db: Session) -> dict:
    service = JobService(db)
    now = utcnow()
    created_runs = service.scan_due_jobs()

    return {
        "scanned_at": now.isoformat(),
        "created_runs": len(created_runs),
        "run_ids": [run.id for run in created_runs],
    }


def scheduler_status() -> dict:
    return {"status": "running", "mode": "db-lock", "leader": "single-active-by-db-lock"}
