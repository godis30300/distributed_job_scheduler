import uuid

import pytest
from fastapi import HTTPException

from app.controllers.job_controller import create_job, set_job_enabled, update_job
from app.core.database import SessionLocal, init_db
from app.models.user import User
from app.schemas.job_schema import JobCreate, JobUpdate


def setup_module(module) -> None:
    init_db()


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_user(db_session) -> User:
    suffix = uuid.uuid4().hex
    user = User(
        username=f"job_controller_user_{suffix}",
        email=f"job_controller_user_{suffix}@example.com",
        password_hash=f"hash-{suffix}",
        role="operator",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def unique_job_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def test_create_job_manual_keeps_next_run_empty_and_normalizes_payload(db_session) -> None:
    current_user = create_test_user(db_session)
    job_name = unique_job_name("manual_job")

    job = create_job(
        db_session,
        JobCreate(
            name=job_name,
            task_type="shell",
            script="echo hello",
            working_dir="manual-job-dir",
            schedule_type="manual",
            timeout_seconds=30,
            retry_limit=1,
            status="enabled",
        ),
        current_user,
    )

    assert job.name == job_name
    assert job.task_name == job_name
    assert job.action_type == "shell"
    assert job.action_payload["script"] == "echo hello"
    assert job.action_payload["working_dir"] == "manual-job-dir"
    assert job.schedule_rule == "manual"
    assert job.next_run_at is None


def test_create_job_interval_sets_schedule_and_next_run(db_session) -> None:
    current_user = create_test_user(db_session)
    job_name = unique_job_name("interval_job")

    job = create_job(
        db_session,
        JobCreate(
            task_name=job_name,
            action="python",
            action_payload={"script": "print('hi')"},
            schedule_type="interval",
            interval_seconds=45,
            timeout_seconds=30,
            retry_limit=2,
            enabled=True,
        ),
        current_user,
    )

    assert job.schedule_rule == "every:45s"
    assert job.enabled is True
    assert job.status == "enabled"
    assert job.next_run_at is not None


def test_create_job_rejects_duplicate_task_name(db_session) -> None:
    current_user = create_test_user(db_session)
    job_name = unique_job_name("duplicate_job")
    create_job(
        db_session,
        JobCreate(task_name=job_name, action="shell", schedule_type="manual", timeout_seconds=30),
        current_user,
    )

    with pytest.raises(HTTPException, match="Job task_name already exists"):
        create_job(
            db_session,
            JobCreate(task_name=job_name, action="shell", schedule_type="manual", timeout_seconds=30),
            current_user,
        )


def test_update_job_recomputes_schedule_and_payload(db_session) -> None:
    current_user = create_test_user(db_session)
    job = create_job(
        db_session,
        JobCreate(
            task_name=unique_job_name("update_job"),
            action="shell",
            action_payload={"script": "echo before", "working_dir": "before-dir"},
            schedule_type="manual",
            timeout_seconds=30,
        ),
        current_user,
    )

    updated = update_job(
        db_session,
        job.id,
        JobUpdate(
            action="python",
            script="print('after')",
            working_dir="after-dir",
            schedule_type="interval",
            interval_seconds=120,
            enabled=True,
            retry_limit=5,
        ),
    )

    assert updated.action_type == "python"
    assert updated.action_payload["script"] == "print('after')"
    assert updated.action_payload["working_dir"] == "after-dir"
    assert updated.schedule_rule == "every:120s"
    assert updated.max_retry == 5
    assert updated.enabled is True
    assert updated.status == "enabled"
    assert updated.next_run_at is not None


def test_set_job_enabled_toggles_next_run_at(db_session) -> None:
    current_user = create_test_user(db_session)
    job = create_job(
        db_session,
        JobCreate(
            task_name=unique_job_name("toggle_job"),
            action="shell",
            action_payload={"script": "echo toggle"},
            schedule_type="interval",
            interval_seconds=60,
            timeout_seconds=30,
        ),
        current_user,
    )

    disabled = set_job_enabled(db_session, job.id, False)
    assert disabled.enabled is False
    assert disabled.status == "disabled"
    assert disabled.next_run_at is None

    enabled = set_job_enabled(db_session, job.id, True)
    assert enabled.enabled is True
    assert enabled.status == "enabled"
    assert enabled.next_run_at is not None
