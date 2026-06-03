import pytest
import time
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.database.database import SessionLocal, init_db
from app.core.logger import logger
from app.domain.entities.job import Job
from app.domain.entities.job_run import JobRun

client = TestClient(app)

@pytest.fixture(scope="module")
def auth_header():
    username = f"stress_{uuid.uuid4().hex[:8]}"
    password = "testpassword"
    client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": password
    })
    response = client.post("/api/auth/login", json={
        "username": username,
        "password": password
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_event_driven_concurrency(auth_header):
    # Arrange
    # 1. Create 3 jobs that sleep for 5 seconds
    job_ids = []
    for i in range(3):
        task_name = f"stress_task_{i}_{uuid.uuid4().hex[:4]}"
        job_data = {
            "task_name": task_name,
            "action": "shell",
            "script": "sleep 5",
            "schedule_type": "manual",
            "status": "enabled"
        }
        response = client.post("/api/jobs", headers=auth_header, json=job_data)
        assert response.status_code == 200 or response.status_code == 201
        job_ids.append(response.json()["id"])

    logger.info(f"\n[test] Created 3 jobs: {job_ids}")

    # Act
    # 2. Trigger all 3 jobs almost at the same time
    run_ids = []
    start_trigger_time = datetime.now(timezone.utc)
    for jid in job_ids:
        response = client.post(f"/api/jobs/{jid}/run", headers=auth_header)
        run_ids.append(response.json()["run_id"])
    
    logger.info(f"[test] Triggered all jobs at {start_trigger_time}. Run IDs: {run_ids}")

    # 3. Wait for them to finish (they should finish in ~5-7 seconds total if concurrent)
    # If they were sequential, it would take 15+ seconds.
    max_wait = 15
    finished_runs = []
    
    start_wait = time.time()
    while time.time() - start_wait < max_wait:
        db = SessionLocal()
        finished_runs = db.query(JobRun).filter(JobRun.id.in_(run_ids), JobRun.status == "success").all()
        db.close()
        if len(finished_runs) == 3:
            break
        time.sleep(1)

    end_wait_time = time.time()
    total_duration = end_wait_time - start_wait
    
    logger.info(f"[test] All jobs finished in {total_duration:.2f} seconds.")
    
    # Assert
    assert len(finished_runs) == 3, f"Only {len(finished_runs)} jobs finished in time."
    # Total time for 3 concurrent 5s jobs should be much less than 15s
    assert total_duration < 12, "Jobs seem to be running sequentially instead of concurrently!"

    # 4. Verify start times are close to each other
    db = SessionLocal()
    runs = db.query(JobRun).filter(JobRun.id.in_(run_ids)).all()
    db.close()
    
    start_times = [r.start_time for r in runs]
    min_start = min(start_times)
    max_start = max(start_times)
    skew = (max_start - min_start).total_seconds()
    
    logger.info(f"[test] Execution skew (time between first and last start): {skew:.2f}s")
    assert skew < 3, "Jobs did not start close enough to be considered event-driven concurrent."

def test_fault_isolation(auth_header):
    # Arrange
    # Create one bad job (syntax error) and one good job
    bad_task = f"bad_task_{uuid.uuid4().hex[:4]}"
    good_task = f"good_task_{uuid.uuid4().hex[:4]}"
    
    # 1. Bad job (invalid shell)
    client.post("/api/jobs", headers=auth_header, json={
        "task_name": bad_task, "action": "shell", "script": "if then fi", "schedule_type": "manual"
    })
    # 2. Good job
    client.post("/api/jobs", headers=auth_header, json={
        "task_name": good_task, "action": "shell", "script": "echo 'im ok'", "schedule_type": "manual"
    })
    
    db = SessionLocal()
    bad_job = db.query(Job).filter(Job.task_name == bad_task).first()
    good_job = db.query(Job).filter(Job.task_name == good_task).first()
    db.close()
    
    # Act
    # Trigger both
    client.post(f"/api/jobs/{bad_job.id}/run", headers=auth_header)
    client.post(f"/api/jobs/{good_job.id}/run", headers=auth_header)
    
    # Wait and verify
    time.sleep(5)
    
    # Assert
    db = SessionLocal()
    bad_run = db.query(JobRun).filter(JobRun.job_id == bad_job.id).order_by(JobRun.created_at.desc()).first()
    good_run = db.query(JobRun).filter(JobRun.job_id == good_job.id).order_by(JobRun.created_at.desc()).first()
    db.close()
    
    assert bad_run.status == "failed"
    assert good_run.status == "success"
    logger.info("[test] Fault isolation passed: Bad job failed, Good job succeeded.")

if __name__ == "__main__":
    pytest.main([__file__])
