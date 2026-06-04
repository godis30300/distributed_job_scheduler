from typing import Optional, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.domain.entities.job_run import JobRun
from app.domain.entities.job_log import JobLog
from app.infrastructure.repositories.job_run_repository import JobRunRepository
from app.core.logger import logger

class QueueService:
    """
    Domain Service to handle complex cross-entity logic for the job queue.
    """
    def __init__(self, db: Session):
        self.db = db
        self.job_run_repo = JobRunRepository(db)

    def dequeue_and_lock(self, worker_id: str, lock_seconds: int = 3600) -> Optional[JobRun]:
        """
        Atomically find and lock the next available job run.
        """
        run = self.job_run_repo.find_next_run_to_lock()
        
        if not run:
            return None

        now = datetime.now(timezone.utc)
        run.status = "running"
        run.worker_id = worker_id
        run.locked_by = worker_id
        run.locked_until = now + timedelta(seconds=lock_seconds)
        run.start_time = run.start_time or now
        run.heartbeat_at = now
        
        # Logging into DB (Domain event would be better, but keeping current logic for now)
        self.db.add(JobLog(job_run_id=run.id, log_level="info", stream="system", message=f"Locked by {worker_id}"))
        
        self.db.commit()
        self.db.refresh(run)
        return run

    def cleanup_expired_runs(self) -> int:
        """
        Find and release runs that have timed out.
        """
        now = datetime.now(timezone.utc)
        expired_runs = self.job_run_repo.find_expired_runs(now)
        
        for run in expired_runs:
            run.status = "pending"
            run.worker_id = None
            run.locked_by = None
            run.locked_until = None
            self.db.add(JobLog(job_run_id=run.id, log_level="warning", stream="system", message="Expired lock released"))
            
        self.db.commit()
        return len(expired_runs)
