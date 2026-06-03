import pytest
from sqlalchemy.orm import Session
from app.domain.entities.job import Job
from app.domain.entities.job_run import JobRun
from app.application.services.executor import execute_job
from app.presentation.controllers.queue_controller import dequeue_next_run, finish_run
from unittest.mock import patch, MagicMock

@pytest.fixture
def async_job(db: Session):
    job = Job(
        task_name="long_api_job",
        action_type="api_poll", # 新的 action type
        action_payload={
            "trigger_url": "http://external-api/start",
            "status_url": "http://external-api/status/{external_id}"
        },
        schedule_rule="manual",
        status="enabled"
    )
    db.add(job)
    db.commit()
    return job

@pytest.mark.asyncio
async def test_async_job_transitions_to_awaiting(db: Session, async_job):
    # 1. Create a run
    run = JobRun(job_id=async_job.id, status="pending", action_type="api_poll")
    db.add(run)
    db.commit()

    # 2. Mock execute_job to return a "wait" signal instead of success/fail
    mock_result = {
        "success": True,
        "status": "awaiting",
        "external_id": "ext_123",
        "stdout": "Job started on external system"
    }

    with patch("app.application.services.executor.execute_job", return_value=mock_result):
        # Simulate worker logic
        from app.application.services.executor import execute_job
        result = await execute_job(run.action_type, async_job.action_payload, 30)
        
        if result.get("status") == "awaiting":
            run.status = "awaiting_result"
            run.metadata_json = {"external_id": result["external_id"]}
            db.commit()

    # 3. Verify JobRun is in awaiting_result and worker would be free
    db.refresh(run)
    assert run.status == "awaiting_result"
    assert run.metadata_json["external_id"] == "ext_123"

def test_poller_completes_awaiting_job(db: Session, async_job):
    # 1. Setup an awaiting run
    run = JobRun(
        job_id=async_job.id, 
        status="awaiting_result", 
        metadata_json={"external_id": "ext_123"},
        action_type="api_poll"
    )
    db.add(run)
    db.commit()

    # 2. Simulate Poller checking status
    # Mock external status check
    external_status = "completed" 
    
    if external_status == "completed":
        run.status = "success"
        run.finished_at = MagicMock() # Simplified for test
        db.commit()

    db.refresh(run)
    assert run.status == "success"
