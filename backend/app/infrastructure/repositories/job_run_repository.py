from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.domain.entities.job_run import JobRun
from app.domain.entities.job import Job
from app.infrastructure.repositories.base_repository import BaseRepository

class JobRunRepository(BaseRepository[JobRun]):
    def __init__(self, db: Session):
        super().__init__(JobRun, db)

    def find_next_run_to_lock(self, excluded_run_ids: set[str] | None = None) -> Optional[JobRun]:
        """
        Implements the core queue logic using SKIP LOCKED.
        Only picks runs from enabled jobs.
        """
        query = (
            self.db.query(JobRun)
            .join(Job, Job.id == JobRun.job_id)
            .filter(JobRun.status == "pending")
            .filter(Job.enabled.is_(True))
            .filter(Job.status.in_(("enabled", "active")))
        )
        if excluded_run_ids:
            query = query.filter(JobRun.id.notin_(excluded_run_ids))
        return query.order_by(JobRun.created_at.asc()).with_for_update(skip_locked=True).first()

    def get_active_runs(self, worker_id: Optional[str] = None) -> List[JobRun]:
        """Fetch all currently running jobs, optionally filtered by worker."""
        if worker_id:
            return self.list(status="running", worker_id=worker_id)
        return self.list(status="running")

    def find_expired_runs(self, now: datetime) -> List[JobRun]:
        """Find runs that have timed out based on locked_until."""
        return (
            self.db.query(JobRun)
            .filter(JobRun.status == "running")
            .filter(JobRun.locked_until.isnot(None))
            .filter(JobRun.locked_until < now)
            .all()
        )

    def count_by_status_since(self, status: str | List[str], since: datetime) -> int:
        query = self.db.query(func.count(JobRun.id)).filter(JobRun.created_at >= since)
        if isinstance(status, list):
            query = query.filter(JobRun.status.in_(status))
        else:
            query = query.filter(JobRun.status == status)
        return query.scalar() or 0

    def count_since(self, since: datetime) -> int:
        return self.db.query(func.count(JobRun.id)).filter(JobRun.created_at >= since).scalar() or 0
