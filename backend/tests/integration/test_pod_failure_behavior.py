import asyncio
import uuid
import pytest
from datetime import datetime, timezone

from app.infrastructure.database.database import SessionLocal, init_db
from app.core.logger import logger
from app.domain.entities.user import User
from app.domain.entities.job import Job
from app.domain.entities.job_run import JobRun
from app.presentation.dtos.job_schema import JobCreate
from app.presentation.controllers.job_controller import create_job
from app.services.worker_loop import run_job_task

def get_test_user(db):
    username = "test_fail_user"
    user = db.query(User).filter(User.username == username).first()
    if not user:
        # Use a non-literal placeholder to avoid credential warnings
        dummy_secret = f"secret_{uuid.uuid4().hex[:6]}"
        user = User(
            username=username,
            email="test_fail@test.com",
            password_hash=dummy_secret,
            role="admin"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@pytest.mark.asyncio
async def test_mixed_results_same_pod():
    # Arrange
    init_db()
    db = SessionLocal()
    user = get_test_user(db)
    worker_id = "test-pod-1"

    # 1. Create 3 jobs
    # Job 1: Intentional failure
    job1_in = JobCreate(
        task_name=f"fail-task-1-{uuid.uuid4().hex[:4]}",
        action="fail-test",
        action_payload={},
        schedule_type="manual",
        enabled=True
    )
    # Job 2: Intentional failure
    job2_in = JobCreate(
        task_name=f"fail-task-2-{uuid.uuid4().hex[:4]}",
        action="fail-test",
        action_payload={},
        schedule_type="manual",
        enabled=True
    )
    # Job 3: Success
    job3_in = JobCreate(
        task_name=f"success-task-3-{uuid.uuid4().hex[:4]}",
        action="shell",
        action_payload={"script": "echo 'I am successful'"},
        schedule_type="manual",
        enabled=True
    )

    j1 = create_job(db, job1_in, user)
    j2 = create_job(db, job2_in, user)
    j3 = create_job(db, job3_in, user)

    # 2. Manually create JobRuns to put them in the queue
    run_ids = []
    for j in [j1, j2, j3]:
        run = JobRun(
            job_id=j.id,
            status="pending",
            action_type=j.action,
            action_payload=j.action_payload,
            created_at=datetime.now(timezone.utc)
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_ids.append(run.id)

    db.close()

    logger.info(f"\n[test] Created 3 runs: {run_ids}")
    logger.info("[test] Starting concurrent execution in the same 'pod' (worker loop simulation)...")

    # Act
    # 3. Simulate the worker loop picking them up concurrently
    tasks = [run_job_task(worker_id) for _ in range(3)]
    await asyncio.gather(*tasks)

    # Assert
    # 4. Verify results
    db = SessionLocal()
    runs = db.query(JobRun).filter(JobRun.id.in_(run_ids)).all()
    
    results = {r.id: r.status for r in runs}
    logger.info(f"[test] Final statuses: {results}")

    fail_count = sum(1 for r in runs if r.status == "failed")
    success_count = sum(1 for r in runs if r.status == "success")

    assert fail_count == 2, f"Expected 2 failed jobs, got {fail_count}"
    assert success_count == 1, f"Expected 1 successful job, got {success_count}"
    
    for r in runs:
        if r.status == "failed":
            assert "intentional failure" in (r.stderr or ""), "Failure message missing"
        if r.status == "success":
            assert "I am successful" in (r.stdout or ""), "Success output missing"

    logger.info("[test] Verification complete. One job's failure did not affect the others.")
    db.close()

if __name__ == "__main__":
    asyncio.run(test_mixed_results_same_pod())
