import pytest
from uuid import uuid4
from datetime import datetime, timezone
from app.infrastructure.database.database import SessionLocal, init_db
from app.domain.entities.user import User
from app.presentation.dtos.job_schema import JobCreate
from app.application.services.job_service import JobService

@pytest.fixture(scope="module")
def db():
    init_db()
    _db = SessionLocal()
    yield _db
    _db.close()

@pytest.fixture
def test_user(db):
    username = f"user_{uuid4().hex[:6]}"
    user = User(username=username, email=f"{username}@test.com", password_hash="hash")
    db.add(user)
    db.commit()
    return user

def test_create_job_syncs_domain_logic(db, test_user):
    # Arrange
    job_service = JobService(db)
    task_name = f"task_{uuid4().hex[:6]}"
    job_in = JobCreate(
        task_name=task_name,
        action="shell",
        schedule_type="interval",
        interval_seconds=600,
        status="enabled"
    )

    # Act
    job = job_service.create_job(job_in, test_user.id)

    # Assert
    assert job.task_name == task_name
    assert job.enabled is True
    assert job.next_run_at is not None
    assert job.action_type == "shell"

def test_create_duplicate_job_raises_error(db, test_user):
    # Arrange
    job_service = JobService(db)
    task_name = f"dup_{uuid4().hex[:6]}"
    job_in = JobCreate(
        task_name=task_name,
        action="shell",
        schedule_type="manual"
    )
    job_service.create_job(job_in, test_user.id)

    # Act
    with pytest.raises(ValueError) as excinfo:
        job_service.create_job(job_in, test_user.id)
    
    # Assert
    assert "already exists" in str(excinfo.value)
