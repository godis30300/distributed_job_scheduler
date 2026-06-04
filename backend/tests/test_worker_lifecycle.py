import time
import uuid
from datetime import datetime, timedelta, timezone

from app.presentation.controllers.job_controller import create_job
from app.presentation.controllers.queue_controller import dequeue_next_run, finish_run, add_log
from app.presentation.controllers.scheduler_controller import scan_due_jobs
from app.infrastructure.database.database import SessionLocal, init_db
from app.core.logger import logger
from app.domain.entities.user import User
from app.domain.entities.job import Job
from app.domain.entities.job_run import JobRun
from app.presentation.dtos.job_schema import JobCreate
import asyncio
from app.application.services.executor import execute_job

def setup_module(module):
    init_db()

def get_test_user(db):
    user = db.query(User).filter(User.username == "test_worker_user").first()
    if not user:
        user = User(
            username="test_worker_user",
            email="test_worker@example.com",
            password_hash="no-hash",
            role="admin"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def test_full_job_cycle():
    # Arrange
    db = SessionLocal()
    try:
        user = get_test_user(db)
        
        # Clear old data to avoid interference
        db.query(JobRun).delete()
        db.query(Job).delete()
        db.commit()

        # 1. Create a job that is due immediately
        task_name = f"test-task-{uuid.uuid4()}"
        job_in = JobCreate(
            task_name=task_name,
            action="shell",
            action_payload={"script": "hello.sh", "args": ["world"]},
            schedule_type="interval",
            interval_seconds=60,
            timeout_seconds=30,
            retry_limit=3,
            enabled=True
        )
        job = create_job(db, job_in, user)
        
        # Verify job state immediately after creation
        assert job.enabled is True
        assert job.status == "enabled"
        
        # Force it to be due
        job.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        db.refresh(job)

        # 2. Run scheduler scan
        result = scan_due_jobs(db)
        assert result["created_runs"] >= 1
        run_id = result["run_ids"][-1]
        
        # Verify JobRun in DB
        run_in_db = db.query(JobRun).filter(JobRun.id == run_id).first()
        assert run_in_db.status == "pending"
        assert run_in_db.job.enabled is True
        assert run_in_db.job.status == "enabled"

        # 3. Worker: Dequeue and lock
        worker_id = "test-worker-1"
        run = dequeue_next_run(db, worker_id)
        
        if run is None:
            # Diagnostic logs
            logger.error(f"Failed to dequeue run {run_id}. Checking actual states...")
            actual_run = db.query(JobRun).filter(JobRun.id == run_id).first()
            logger.error(f"Run status: {actual_run.status}, Job Enabled: {actual_run.job.enabled}, Job Status: {actual_run.job.status}")

        assert run is not None
        assert run.id == run_id
        assert run.status == "running"

        # 4. Worker: Execute
        exec_result = asyncio.run(execute_job(run.action_type, run.action_payload, run.timeout_seconds))
        
        # 5. Worker: Finish
        finish_run(db, run.id, "success", stdout=exec_result["stdout"], stderr=exec_result["stderr"])
        
        # 6. Verify final state
        db.refresh(run)
        assert run.status == "success"
        logger.info("Job cycle test passed!")

    finally:
        db.close()
