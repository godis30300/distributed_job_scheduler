import pytest
from datetime import datetime, timedelta, timezone
from app.services.schedule_utils import compute_next_run
from app.domain.entities.job import Job

def test_compute_next_run_interval():
    # Arrange
    base = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)
    
    # Act
    r30s = compute_next_run("every:30s", base_time=base)
    r5m = compute_next_run("every:5m", base_time=base)
    r1h = compute_next_run("every:1h", base_time=base)

    # Assert
    assert r30s == base + timedelta(seconds=30)
    assert r5m == base + timedelta(minutes=5)
    assert r1h == base + timedelta(hours=1)

def test_job_model_sync_logic():
    # Arrange
    job = Job(
        task_name="test-sync",
        action_type="shell",
        schedule_rule="every:10m",
        status="enabled"
    )
    
    # Act
    job.sync_domain_logic()
    
    # Assert
    assert job.enabled is True
    assert job.next_run_at is not None

def test_job_model_disable_logic():
    # Arrange
    job = Job(
        task_name="test-disable",
        action_type="shell",
        schedule_rule="every:10m",
        status="enabled"
    )
    job.sync_domain_logic()

    # Act
    job.status = "disabled"
    job.sync_domain_logic()

    # Assert
    assert job.enabled is False
    assert job.next_run_at is None
