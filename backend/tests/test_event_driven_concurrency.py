import pytest
import asyncio
import time
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.database.database import SessionLocal, init_db
from app.core.logger import logger
from app.domain.entities.job import Job
from app.domain.entities.job_run import JobRun
from app.services.worker_loop import run_job_task

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

@pytest.mark.asyncio
async def test_event_driven_concurrency(auth_header):
    # Arrange
    # 1. Create 3 jobs that sleep for 5 seconds
    job_ids = []
    for i in range(3):
        task_name = f"stress_task_{i}_{uuid.uuid4().hex[:4]}"
        job_data = {
            "task_name": task_name,
            "action": "shell",
            "script": "sleep 1", # Reduce to 1s for faster CI
            "schedule_type": "manual",
            "status": "enabled"
        }
        response = client.post("/api/jobs", headers=auth_header, json=job_data)
        assert response.status_code == 200 or response.status_code == 201
        job_ids.append(response.json()["id"])

    # Act
    # 2. Trigger all 3 jobs
    run_ids = []
    for jid in job_ids:
        response = client.post(f"/api/jobs/{jid}/run", headers=auth_header)
        run_ids.append(response.json()["run_id"])
    
    # 3. Start local worker tasks to process them
    worker_id = "test-worker-concurrency"
    tasks = [run_job_task(worker_id) for _ in range(3)]
    await asyncio.gather(*tasks)

    # Assert
    db = SessionLocal()
    finished_runs = db.query(JobRun).filter(JobRun.id.in_(run_ids), JobRun.status == "success").all()
    db.close()
    
    assert len(finished_runs) == 3, f"Only {len(finished_runs)} jobs finished."

@pytest.mark.asyncio
async def test_fault_isolation(auth_header):
    # Arrange
    bad_task = f"bad_task_{uuid.uuid4().hex[:4]}"
    good_task = f"good_task_{uuid.uuid4().hex[:4]}"
    
    client.post("/api/jobs", headers=auth_header, json={
        "task_name": bad_task, "action": "shell", "script": "exit 1", "schedule_type": "manual"
    })
    client.post("/api/jobs", headers=auth_header, json={
        "task_name": good_task, "action": "shell", "script": "echo 'ok'", "schedule_type": "manual"
    })
    
    db = SessionLocal()
    bad_job = db.query(Job).filter(Job.task_name == bad_task).first()
    good_job = db.query(Job).filter(Job.task_name == good_task).first()
    db.close()
    
    # Act
    client.post(f"/api/jobs/{bad_job.id}/run", headers=auth_header)
    client.post(f"/api/jobs/{good_job.id}/run", headers=auth_header)
    
    worker_id = "test-worker-isolation"
    tasks = [run_job_task(worker_id) for _ in range(2)]
    await asyncio.gather(*tasks)
    
    # Assert
    db = SessionLocal()
    bad_run = db.query(JobRun).filter(JobRun.job_id == bad_job.id).order_by(JobRun.created_at.desc()).first()
    good_run = db.query(JobRun).filter(JobRun.job_id == good_job.id).order_by(JobRun.created_at.desc()).first()
    db.close()
    
    assert bad_run.status == "failed"
    assert good_run.status == "success"

if __name__ == "__main__":
    pytest.main([__file__])
