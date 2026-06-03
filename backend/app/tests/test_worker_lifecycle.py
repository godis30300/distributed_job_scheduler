import time
import uuid
from datetime import datetime, timedelta, timezone

from app.controllers.job_controller import create_job
from app.controllers.queue_controller import dequeue_next_run, finish_run, add_log
from app.controllers.scheduler_controller import scan_due_jobs
from app.core.database import SessionLocal, init_db
from app.models.user import User
from app.models.job_run import JobRun
from app.schemas.job_schema import JobCreate
import asyncio
from app.services.executor import execute_job

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
    db = SessionLocal()
    try:
        user = get_test_user(db)
        
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
        print(f"Created job: {job.task_name}")

        # Force it to be due by setting next_run_at to past
        job.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

        # 2. Run scheduler scan
        result = scan_due_jobs(db)
        assert result["created_runs"] >= 1
        run_id = result["run_ids"][-1]
        print(f"Scheduler created run: {run_id}")

        # 3. Worker: Dequeue and lock
        worker_id = "test-worker-1"
        run = dequeue_next_run(db, worker_id)
        assert run is not None
        assert run.id == run_id
        assert run.status == "running"
        print(f"Worker locked run: {run.id}")

        # 4. Worker: Execute
        # We simulate what worker_loop.py does
        action_type = run.action_type
        action_payload = run.action_payload
        timeout = run.timeout_seconds
        
        exec_result = asyncio.run(execute_job(action_type, action_payload, timeout))
        assert exec_result["success"] is True
        assert "Hello" in exec_result["stdout"]
        print(f"Execution successful: {exec_result['stdout'].strip()}")

        # 5. Worker: Finish
        finish_run(
            db,
            run.id,
            "success",
            stdout=exec_result["stdout"],
            stderr=exec_result["stderr"]
        )
        
        # 6. Verify final state
        db.refresh(run)
        assert run.status == "success"
        assert run.end_time is not None
        assert run.stdout == exec_result["stdout"]
        print("Job cycle test passed!")

    finally:
        db.close()

if __name__ == "__main__":
    test_full_job_cycle()
