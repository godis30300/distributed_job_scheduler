from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.domain.entities.user import User
from app.main import app
from app.presentation.controllers import job_controller, job_run_controller
from app.presentation.dtos.job_schema import JobCreate, JobUpdate


def _create_user(db, role: str = "operator") -> User:
    username = f"{role}_{uuid4().hex[:8]}"
    user = User(
        username=username,
        email=f"{username}@test.com",
        password_hash=f"secret_{uuid4().hex[:8]}",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_job(db, owner: User, task_prefix: str):
    payload = JobCreate(
        task_name=f"{task_prefix}_{uuid4().hex[:8]}",
        action="shell",
        shell_script="echo ok",
        schedule_type="manual",
        status="enabled",
    )
    return job_controller.create_job(db, payload, owner)


def _assert_404(callable_):
    with pytest.raises(HTTPException) as exc_info:
        callable_()
    assert exc_info.value.status_code == 404


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.username)
    return {"Authorization": f"Bearer {token}"}


def test_non_admin_lists_only_owned_jobs(db):
    owner = _create_user(db)
    other = _create_user(db)
    admin = _create_user(db, role="admin")
    own_job = _create_job(db, owner, "own")
    other_job = _create_job(db, other, "other")

    owner_jobs = job_controller.list_jobs(db, current_user=owner)
    admin_jobs = job_controller.list_jobs(db, current_user=admin)

    assert {job.id for job in owner_jobs} == {own_job.id}
    assert {own_job.id, other_job.id}.issubset({job.id for job in admin_jobs})


def test_jobs_api_uses_current_user_scope(db):
    owner = _create_user(db)
    other = _create_user(db)
    own_job = _create_job(db, owner, "api_own")
    other_job = _create_job(db, other, "api_foreign")

    client = TestClient(app)
    list_response = client.get("/api/jobs", headers=_auth_headers(owner))
    detail_response = client.get(f"/api/jobs/{other_job.id}", headers=_auth_headers(owner))

    assert list_response.status_code == 200
    assert {job["id"] for job in list_response.json()} == {own_job.id}
    assert detail_response.status_code == 404


def test_non_admin_cannot_access_or_mutate_other_users_job(db):
    owner = _create_user(db)
    other = _create_user(db)
    other_job = _create_job(db, other, "foreign")

    _assert_404(lambda: job_controller.get_job_or_404(db, other_job.id, owner))
    _assert_404(lambda: job_controller.update_job(db, other_job.id, JobUpdate(description="blocked"), owner))
    _assert_404(lambda: job_controller.delete_job(db, other_job.id, owner))
    _assert_404(lambda: job_controller.set_job_enabled(db, other_job.id, False, owner))
    _assert_404(lambda: job_controller.trigger_job(db, other_job.id, owner))


def test_admin_can_access_other_users_job(db):
    other = _create_user(db)
    admin = _create_user(db, role="admin")
    other_job = _create_job(db, other, "admin_visible")

    assert job_controller.get_job_or_404(db, other_job.id, admin).id == other_job.id
    updated = job_controller.update_job(db, other_job.id, JobUpdate(description="allowed"), admin)

    assert updated.description == "allowed"


def test_non_admin_cannot_see_other_users_job_runs_or_logs(db):
    owner = _create_user(db)
    other = _create_user(db)
    own_job = _create_job(db, owner, "own_run")
    other_job = _create_job(db, other, "foreign_run")
    own_run = job_controller.trigger_job(db, own_job.id, owner)
    other_run = job_controller.trigger_job(db, other_job.id, other)
    job_run_controller.save_job_log(db, other_run.id, "info", "foreign log")

    visible_runs = job_run_controller.list_job_runs(db, current_user=owner)

    assert {run.id for run in visible_runs} == {own_run.id}
    _assert_404(lambda: job_run_controller.get_run_or_404(db, other_run.id, owner))
    _assert_404(lambda: job_run_controller.list_logs(db, other_run.id, owner))
    assert job_run_controller.search_job_logs(db, current_user=owner) == []
