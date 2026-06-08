from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.domain.entities.job import Job
from app.domain.entities.job_run import JobRun
from app.domain.entities.job_log import JobLog
from app.domain.exceptions import EntityNotFoundError, BusinessRuleViolationError
from app.infrastructure.repositories.job_run_repository import JobRunRepository

class JobRunService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = JobRunRepository(db)

    def get_run(self, run_id: str) -> JobRun:
        run = self.repository.get(run_id)
        if not run:
            raise EntityNotFoundError(f"Job run {run_id} not found")
        return run

    def dequeue_next_run(self, worker_name: str, lock_seconds: int = 3600) -> JobRun | None:
        """Lock the next available pending job run using repository logic."""
        skipped_run_ids: set[str] = set()
        while True:
            run = self.repository.find_next_run_to_lock(skipped_run_ids)
            if not run:
                return None
            if not run.job or run.job.are_dependencies_satisfied(self.db):
                break
            skipped_run_ids.add(run.id)


        now = datetime.now(timezone.utc)
        run.status = "running"
        run.worker_id = worker_name
        run.locked_by = worker_name
        run.locked_until = now + timedelta(seconds=lock_seconds)
        run.start(now) # Use Rich Domain Model logic
        
        self.db.add(JobLog(job_run_id=run.id, log_level="info", stream="system", message=f"Locked by {worker_name}"))
        self.repository.commit()
        self.repository.refresh(run)
        return run

    def update_status(self, run_id: str, status: str, stdout: str = None, stderr: str = None, error_message: str = None) -> JobRun:
        run = self.get_run(run_id)
        now = datetime.now(timezone.utc)

        if status == "running":
            run.start(now)
        elif status in ("success", "failed", "timeout", "canceled"):
            run.status = status
            run.complete(now) # Use Rich Domain Model logic
            self.db.add(JobLog(job_run_id=run.id, log_level="info", stream="system", message=f"Run finished: {status}"))
            
            # Automatic Retry Logic
            if status in ("failed", "timeout") and run.job:
                if run.retry_count < run.job.max_retry:
                    self.db.flush() # Ensure current run status is saved for the retry logic
                    try:
                        new_run = self.retry_run(run.id)
                        self.db.add(JobLog(job_run_id=run.id, log_level="info", stream="system", message=f"Automatic retry triggered: {new_run.id}"))
                    except Exception as e:
                        self.db.add(JobLog(job_run_id=run.id, log_level="error", stream="system", message=f"Failed to trigger automatic retry: {e}"))

        if stdout is not None:
            run.stdout = stdout
            if stdout:
                self.db.add(JobLog(job_run_id=run.id, log_level="info", stream="stdout", message=stdout))
        if stderr is not None:
            run.stderr = stderr
            if stderr:
                self.db.add(JobLog(job_run_id=run.id, log_level="error", stream="stderr", message=stderr))
        if error_message is not None:
            run.error_message = error_message
            if error_message:
                self.db.add(JobLog(job_run_id=run.id, log_level="error", stream="system", message=error_message))

        self.repository.commit()
        self.repository.refresh(run)
        return run

    def release_expired_locks(self) -> int:
        now = datetime.now(timezone.utc)
        expired_runs = self.repository.find_expired_runs(now)

        for run in expired_runs:
            run.status = "pending"
            run.worker_id = None
            run.locked_by = None
            run.locked_until = None
            run.heartbeat_at = now
            self.db.add(JobLog(job_run_id=run.id, log_level="warning", stream="system", message="Expired lock released"))

        self.repository.commit()
        return len(expired_runs)

    def heartbeat(self, run_id: str) -> JobRun:
        run = self.get_run(run_id)
        run.heartbeat_at = datetime.now(timezone.utc)
        self.repository.commit()
        self.repository.refresh(run)
        return run

    def retry_run(self, run_id: str, user_id: str = None) -> JobRun:
        run = self.get_run(run_id)
        if run.status not in ("failed", "timeout", "canceled"):
            raise BusinessRuleViolationError("Only terminal failed runs can be retried")
        
        if run.job and run.retry_count >= run.job.max_retry:
            raise BusinessRuleViolationError("Retry limit reached")

        new_run = JobRun(
            job_id=run.job_id,
            user_id=user_id or run.user_id,
            status="pending",
            trigger_type="retry",
            triggered_by="retry",
            retry_count=run.retry_count + 1,
            action_type=run.action_type,
            action_payload=run.action_payload,
            timeout_seconds=run.timeout_seconds,
        )
        self.repository.add(new_run)
        self.db.add(JobLog(job_run_id=run.id, log_level="info", stream="system", message=f"Retry created: {new_run.id}"))
        self.repository.commit()
        self.repository.refresh(new_run)
        return new_run
