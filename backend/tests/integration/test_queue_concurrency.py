import pytest
import uuid
from datetime import datetime, timezone
from app.infrastructure.database.database import SessionLocal, init_db
from app.domain.entities.job import Job
from app.domain.entities.job_run import JobRun
from app.domain.entities.user import User
from app.presentation.controllers.queue_controller import lock_pending_job

def setup_module(module):
    init_db()
    db = SessionLocal()
    db.query(JobRun).delete()
    db.query(Job).delete()
    db.commit()
    db.close()

def get_test_user(db):
    user = db.query(User).filter(User.username == "test_queue_user").first()
    if not user:
        user = User(username="test_queue_user", email="test_queue@example.com", password_hash="no-hash")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def test_concurrency_lock_skip_locked():
    # Arrange
    db_setup = SessionLocal()
    db_setup.query(JobRun).delete()
    db_setup.commit()
    
    user = get_test_user(db_setup)
    job = Job(task_name=f"q-test-{uuid.uuid4().hex[:4]}", action_type="shell", schedule_rule="manual", status="enabled", user_id=user.id)
    job.sync_domain_logic()
    db_setup.add(job)
    db_setup.commit()
    
    run = JobRun(job_id=job.id, status="pending", action_type=job.action_type, created_at=datetime.now(timezone.utc))
    db_setup.add(run)
    db_setup.commit()
    run_id = run.id
    db_setup.close()

    db1 = SessionLocal()
    db2 = SessionLocal()
    try:
        # Act
        # Debug: Check if it exists in db1
        exists = db1.query(JobRun).filter(JobRun.id == run_id).first()
        print(f"DEBUG - run_id {run_id} exists in db1: {exists is not None}")
        
        # DB1 starts a transaction and locks the row
        r1 = db1.query(JobRun).filter(JobRun.id == run_id).with_for_update(skip_locked=True).first()
        
        # DB2 tries to lock the same row
        r2 = db2.query(JobRun).filter(JobRun.id == run_id).with_for_update(skip_locked=True).first()
        
        # Assert
        assert r1 is not None, "DB1 should have found and locked the run"
        assert r2 is None, "DB2 should have skipped the locked run"
        
        db1.rollback()
        db2.rollback()
    finally:
        db1.close()
        db2.close()

def test_lock_pending_job_updates_fields():
    # Arrange
    db_setup = SessionLocal()
    db_setup.query(JobRun).delete()  # Ensure clean state for this test
    db_setup.commit()
    
    user = get_test_user(db_setup)
    job = Job(task_name=f"f-test-{uuid.uuid4().hex[:4]}", action_type="shell", schedule_rule="manual", status="enabled", user_id=user.id)
    job.sync_domain_logic()
    db_setup.add(job)
    db_setup.commit()
    
    run = JobRun(job_id=job.id, status="pending", action_type=job.action_type, created_at=datetime.now(timezone.utc))
    db_setup.add(run)
    db_setup.commit()
    run_id = run.id
    job_id = job.id
    db_setup.close()

    db = SessionLocal()
    worker_name = "test-worker-alpha"
    
    # Debug prints
    check_job = db.query(Job).filter(Job.id == job_id).first()
    check_run = db.query(JobRun).filter(JobRun.id == run_id).first()
    print(f"DEBUG - Job state before lock: id={check_job.id if check_job else 'NONE'}, enabled={check_job.enabled if check_job else 'N/A'}, status={check_job.status if check_job else 'N/A'}")
    print(f"DEBUG - JobRun state before lock: id={check_run.id if check_run else 'NONE'}, job_id={check_run.job_id if check_run else 'N/A'}, status={check_run.status if check_run else 'N/A'}")

    # Act
    locked_run = lock_pending_job(db, worker_name)
    
    # Assert
    assert locked_run is not None
    assert locked_run.id == run_id
    assert locked_run.status == "running"
    assert locked_run.worker_id == worker_name
    db.close()
