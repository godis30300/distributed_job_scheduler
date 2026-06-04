import pytest
from uuid import uuid4
from datetime import timedelta
from sqlalchemy.orm import Session
from app.infrastructure.database.database import SessionLocal, init_db
from app.domain.entities.job import Job
from app.domain.entities.job_run import JobRun
from app.domain.entities.job_dependency import JobDependency
from app.domain.entities.user import User
from app.application.services.job_service import JobService
from app.presentation.controllers.scheduler_controller import scan_due_jobs
from app.presentation.controllers.job_controller import trigger_job
from app.presentation.dtos.job_schema import JobCreate
from app.services.schedule_utils import utcnow
from fastapi import HTTPException

def test_job_dependency_blocks_execution(db: Session):
    # Clear existing data
    db.query(JobDependency).delete()
    db.query(JobRun).delete()
    db.query(Job).delete()
    db.commit()

    # 1. Create Job A (Dependency)
    job_a = Job(
        task_name="job_a",
        action_type="shell",
        schedule_rule="*/5 * * * *",
        status="enabled",
        next_run_at=utcnow() - timedelta(minutes=1)
    )
    db.add(job_a)
    db.commit()

    # 2. Create Job B (Dependent on A)
    job_b = Job(
        task_name="job_b",
        action_type="shell",
        schedule_rule="*/5 * * * *",
        status="enabled",
        next_run_at=utcnow() - timedelta(minutes=1)
    )
    db.add(job_b)
    db.commit()

    dep = JobDependency(job_id=job_b.id, depends_on_job_id=job_a.id, required_status="success")
    db.add(dep)
    db.commit()

    # 3. Scan jobs - Job A should run, Job B should be blocked
    result = scan_due_jobs(db)
    assert result["created_runs"] == 1
    
    runs_a = db.query(JobRun).filter(JobRun.job_id == job_a.id).all()
    runs_b = db.query(JobRun).filter(JobRun.job_id == job_b.id).all()
    assert len(runs_a) == 1
    assert len(runs_b) == 0

def test_job_multiple_dependencies_success(db: Session):
    db.query(JobDependency).delete()
    db.query(JobRun).delete()
    db.query(Job).delete()
    db.commit()

    job_a = Job(task_name="job_a", action_type="shell", schedule_rule="manual", status="enabled")
    job_b = Job(task_name="job_b", action_type="shell", schedule_rule="manual", status="enabled")
    job_c = Job(task_name="job_c", action_type="shell", schedule_rule="*/5 * * * *", status="enabled", next_run_at=utcnow() - timedelta(minutes=1))
    db.add_all([job_a, job_b, job_c])
    db.commit()

    db.add(JobDependency(job_id=job_c.id, depends_on_job_id=job_a.id, required_status="success"))
    db.add(JobDependency(job_id=job_c.id, depends_on_job_id=job_b.id, required_status="success"))
    db.commit()

    # Only A succeeded
    db.add(JobRun(job_id=job_a.id, status="success", action_type="shell"))
    db.commit()
    assert scan_due_jobs(db)["created_runs"] == 0

    # Now B succeeded
    db.add(JobRun(job_id=job_b.id, status="success", action_type="shell"))
    db.commit()
    assert scan_due_jobs(db)["created_runs"] == 1

def test_job_service_create_with_dependencies(db: Session, test_user):
    db.query(JobDependency).delete()
    db.query(JobRun).delete()
    db.query(Job).delete()
    db.commit()

    job_service = JobService(db)
    job_service.create_job(
        JobCreate(task_name="upstream", action="shell", schedule_type="manual"),
        test_user.id
    )
    downstream = job_service.create_job(
        JobCreate(task_name="downstream", action="shell", schedule_type="manual", depends_on=["upstream"]),
        test_user.id
    )
    
    deps = db.query(JobDependency).filter(JobDependency.job_id == downstream.id).all()
    assert len(deps) == 1
    upstream = db.query(Job).filter(Job.task_name == "upstream").first()
    assert deps[0].depends_on_job_id == upstream.id

def test_manual_trigger_respects_dependencies(db: Session, test_user):
    db.query(JobDependency).delete()
    db.query(JobRun).delete()
    db.query(Job).delete()
    db.commit()

    job_a = Job(task_name="job_a", action_type="shell", schedule_rule="manual", status="enabled")
    job_b = Job(task_name="job_b", action_type="shell", schedule_rule="manual", status="enabled")
    db.add_all([job_a, job_b])
    db.commit()

    db.add(JobDependency(job_id=job_b.id, depends_on_job_id=job_a.id, required_status="success"))
    db.commit()

    # Trigger B manually - should FAIL
    with pytest.raises(HTTPException) as excinfo:
        trigger_job(db, job_b.id, test_user)
    assert excinfo.value.status_code == 400

    # Simulate A success
    db.add(JobRun(job_id=job_a.id, status="success", action_type="shell"))
    db.commit()

    # Trigger B manually - should SUCCESS
    run_b = trigger_job(db, job_b.id, test_user)
    assert run_b.job_id == job_b.id
