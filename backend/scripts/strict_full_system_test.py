from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.database import SessionLocal
from app.domain.entities.user import User


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api").rstrip("/")
USERNAME = f"strict_user_{int(time.time())}"
PASSWORD = "StrictPass123!"
NEW_PASSWORD = "StrictPass456!"


def step(message: str) -> None:
    print(f"[strict-test] {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def request_json(client: httpx.Client, method: str, path: str, expected_status: int = 200, **kwargs) -> Any:
    response = client.request(method, f"{API_BASE_URL}{path}", timeout=20, **kwargs)
    if response.status_code != expected_status:
        raise AssertionError(
            f"{method} {path} expected HTTP {expected_status}, got HTTP {response.status_code}: {response.text[:500]}"
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return response.text


def wait_for_terminal_run(client: httpx.Client, token: str, run_id: str, seconds: int = 30) -> dict[str, Any]:
    headers = auth_headers(token)
    deadline = time.time() + seconds
    last_run: dict[str, Any] | None = None
    while time.time() < deadline:
        last_run = request_json(client, "GET", f"/job-runs/{run_id}", headers=headers)
        if last_run["status"] in {"success", "failed", "timeout", "canceled"}:
            return last_run
        time.sleep(1)
    raise TimeoutError(f"run did not finish in {seconds}s: {run_id}; last={last_run}")


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client: httpx.Client, username: str, password: str) -> str:
    response = request_json(client, "POST", "/auth/login", json={"username": username, "password": password})
    token = response["access_token"]
    require(token, "login must return access_token")
    return token


def assert_registered_password_hash(username: str, plain_password: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        require(user is not None, "registered user must exist in DB")
        require(user.password_hash != plain_password, "password_hash must not store plaintext")
        require(user.password_hash.startswith("$2b$"), "password_hash must be bcrypt")
        require(len(user.password_hash) == 60, "bcrypt hash length should be 60")
    finally:
        db.close()


def create_job(client: httpx.Client, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return request_json(client, "POST", "/jobs", headers=auth_headers(token), json=payload)


def trigger_run(client: httpx.Client, token: str, job_id: str, alias: str = "run") -> str:
    response = request_json(client, "POST", f"/jobs/{job_id}/{alias}", headers=auth_headers(token))
    return response["run_id"]


def assert_log_search(client: httpx.Client, token: str, task_name: str, status: str) -> None:
    logs = request_json(
        client,
        "GET",
        f"/job-runs/logs/search?task_name={task_name}&status={status}&limit=50&offset=0",
        headers=auth_headers(token),
    )
    require(isinstance(logs, list), "log search must return a list")
    require(logs, f"log search should find logs for {task_name}/{status}")


def main() -> int:
    try:
        suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        with httpx.Client() as client:
            step("system health endpoints without seed account")
            health = request_json(client, "GET", "/health")
            system_health = request_json(client, "GET", "/system/health")
            version = request_json(client, "GET", "/system/version")
            require(health["status"] == "healthy", "/api/health must be healthy")
            require(system_health["status"] == "healthy", "/api/system/health must be healthy")
            require(version["service"] == "distributed-job-scheduler", "/api/system/version service mismatch")

            step("real register/login/password hash flow")
            registered = request_json(
                client,
                "POST",
                "/auth/register",
                json={
                    "username": USERNAME,
                    "email": f"{USERNAME}@example.com",
                    "password": PASSWORD,
                    "role": "operator",
                },
            )
            require(registered["username"] == USERNAME, "register must return created user")
            assert_registered_password_hash(USERNAME, PASSWORD)

            token = login(client, USERNAME, PASSWORD)
            me = request_json(client, "GET", "/auth/me", headers=auth_headers(token))
            require(me["username"] == USERNAME, "/auth/me must return current user")

            request_json(
                client,
                "PUT",
                "/auth/password",
                headers=auth_headers(token),
                json={"old_password": PASSWORD, "new_password": NEW_PASSWORD},
            )
            request_json(client, "POST", "/auth/login", expected_status=401, json={"username": USERNAME, "password": PASSWORD})
            token = login(client, USERNAME, NEW_PASSWORD)
            request_json(client, "POST", "/auth/logout")

            step("new-format shell job CRUD and execution")
            shell_name = f"strict-shell-{suffix}"
            shell_job = create_job(
                client,
                token,
                {
                    "name": shell_name,
                    "task_type": "shell",
                    "script": f"echo strict-shell-{suffix}",
                    "description": "strict shell job",
                    "working_dir": shell_name,
                    "schedule_type": "manual",
                    "timeout_seconds": 30,
                    "retry_limit": 1,
                    "status": "enabled",
                },
            )
            require(shell_job["name"] == shell_name, "shell job name mismatch")
            require(shell_job["task_type"] == "shell", "shell task_type mismatch")
            request_json(client, "GET", f"/jobs/{shell_job['id']}", headers=auth_headers(token))
            listed_jobs = request_json(client, "GET", f"/jobs?keyword={shell_name}", headers=auth_headers(token))
            require(any(job["id"] == shell_job["id"] for job in listed_jobs), "list jobs keyword should find shell job")
            disabled = request_json(client, "PATCH", f"/jobs/{shell_job['id']}/disable", headers=auth_headers(token))
            require(disabled["status"] == "disabled", "disable endpoint should disable job")
            enabled = request_json(client, "PATCH", f"/jobs/{shell_job['id']}/enable", headers=auth_headers(token))
            require(enabled["status"] == "enabled", "enable endpoint should enable job")
            updated = request_json(
                client,
                "PUT",
                f"/jobs/{shell_job['id']}",
                headers=auth_headers(token),
                json={"description": "strict shell job updated", "script": f"echo strict-shell-updated-{suffix}"},
            )
            require(updated["description"] == "strict shell job updated", "update endpoint should update description")
            shell_run = wait_for_terminal_run(client, token, trigger_run(client, token, shell_job["id"]))
            require(shell_run["status"] == "success", "shell run must succeed")
            require(shell_run["duration_seconds_decimal"] > 0, "shell run must have decimal duration")
            require("strict-shell-updated" in (shell_run["stdout"] or ""), "shell stdout must be stored")
            request_json(client, "GET", f"/job-runs/{shell_run['id']}/logs", headers=auth_headers(token))
            assert_log_search(client, token, shell_name, "success")

            step("new-format python job execution through trigger alias")
            python_name = f"strict-python-{suffix}"
            python_job = create_job(
                client,
                token,
                {
                    "name": python_name,
                    "task_type": "python",
                    "script": f"print('strict-python-{suffix}')",
                    "description": "strict python job",
                    "working_dir": python_name,
                    "schedule_type": "manual",
                    "timeout_seconds": 30,
                    "retry_limit": 1,
                    "status": "enabled",
                },
            )
            python_run = wait_for_terminal_run(client, token, trigger_run(client, token, python_job["id"], alias="trigger"))
            require(python_run["status"] == "success", "python run must succeed")
            require("strict-python" in (python_run["stdout"] or ""), "python stdout must be stored")

            step("legacy payload compatibility")
            legacy_name = f"strict-legacy-{suffix}"
            legacy_job = create_job(
                client,
                token,
                {
                    "task_name": legacy_name,
                    "schedule_type": "manual",
                    "action": "shell",
                    "action_payload": {"script": f"echo strict-legacy-{suffix}", "args": []},
                    "timeout_seconds": 30,
                    "max_retry": 1,
                    "status": "enabled",
                },
            )
            legacy_run = wait_for_terminal_run(client, token, trigger_run(client, token, legacy_job["id"]))
            require(legacy_run["status"] == "success", "legacy shell run must succeed")

            step("failed run, retry, cancel, and worker finish paths")
            fail_name = f"strict-fail-{suffix}"
            fail_job = create_job(
                client,
                token,
                {
                    "task_name": fail_name,
                    "schedule_type": "manual",
                    "action": "fail-test",
                    "action_payload": {},
                    "timeout_seconds": 30,
                    "max_retry": 1,
                    "status": "enabled",
                },
            )
            failed_run = wait_for_terminal_run(client, token, trigger_run(client, token, fail_job["id"]))
            require(failed_run["status"] == "failed", "fail-test run must fail")
            retry_run = request_json(client, "POST", f"/job-runs/{failed_run['id']}/retry", headers=auth_headers(token))
            require(retry_run["retry_count"] == failed_run["retry_count"] + 1, "retry must increment retry_count")

            cancel_job = create_job(
                client,
                token,
                {
                    "task_name": f"strict-cancel-{suffix}",
                    "action": "long-task",
                    "action_payload": {},
                    "schedule_type": "manual",
                    "timeout_seconds": 30,
                    "retry_limit": 1,
                    "status": "enabled",
                },
            )
            cancel_run_id = trigger_run(client, token, cancel_job["id"])
            canceled = request_json(client, "POST", f"/job-runs/{cancel_run_id}/cancel", headers=auth_headers(token))
            require(canceled["status"] == "canceled", "cancel endpoint must cancel pending run")

            finish_job = create_job(
                client,
                token,
                {
                    "task_name": f"strict-worker-finish-{suffix}",
                    "action": "long-task",
                    "action_payload": {},
                    "schedule_type": "manual",
                    "timeout_seconds": 30,
                    "retry_limit": 1,
                    "status": "enabled",
                },
            )
            finish_run_id = trigger_run(client, token, finish_job["id"])
            heartbeat = request_json(client, "POST", f"/workers/{finish_run_id}/heartbeat", headers=auth_headers(token))
            require(heartbeat["status"] in {"pending", "running"}, "heartbeat should return current run status")
            finished_by_worker = request_json(
                client,
                "POST",
                f"/workers/{finish_run_id}/finish",
                headers=auth_headers(token),
                json={"status": "success", "stdout": "manual worker finish stdout", "stderr": "", "error_message": None},
            )
            require(finished_by_worker["status"] == "success", "worker finish must mark run success")

            workers = request_json(client, "GET", "/workers", headers=auth_headers(token))
            require(isinstance(workers, list), "workers endpoint must return list")
            pull = request_json(client, "POST", "/workers/pull?worker_id=strict-api-worker", headers=auth_headers(token))
            require("task" in pull, "worker pull must return task key")

            step("scheduler, dashboard, system, metrics, and delete paths")
            scheduler_scan = request_json(client, "POST", "/scheduler/scan", headers=auth_headers(token))
            scheduler_status = request_json(client, "GET", "/scheduler/status", headers=auth_headers(token))
            scheduler_leader = request_json(client, "GET", "/scheduler/leader", headers=auth_headers(token))
            require("created_runs" in scheduler_scan, "scheduler scan must return created_runs")
            require(scheduler_status["status"] == "running", "scheduler status must be running")
            require("leader" in scheduler_leader, "scheduler leader must return leader")

            request_json(client, "GET", "/system/nodes", headers=auth_headers(token))
            request_json(client, "GET", "/system/pods", headers=auth_headers(token))
            summary = request_json(client, "GET", "/dashboard/summary", headers=auth_headers(token))
            require("total_jobs" in summary and "total_runs_today" in summary, "dashboard summary must include counts")

            metrics = client.get(f"{API_BASE_URL}/metrics", timeout=20).text
            for metric_name in (
                "scheduler_api_requests_total",
                "scheduler_job_runs_total",
                "scheduler_queue_length",
                "scheduler_worker_load",
                "scheduler_container_memory_usage_bytes",
                "scheduler_container_cpu_usage_seconds_total",
                "scheduler_pod_restart_count",
            ):
                require(metric_name in metrics, f"metrics must include {metric_name}")

            request_json(client, "DELETE", f"/jobs/{cancel_job['id']}", headers=auth_headers(token))
            deleted_job = request_json(client, "GET", f"/jobs/{cancel_job['id']}", headers=auth_headers(token))
            require(deleted_job["status"] == "deleted", "delete endpoint should soft-delete job")

        print("\nSTRICT FULL SYSTEM TEST PASSED")
        return 0
    except Exception as exc:
        print("\nSTRICT FULL SYSTEM TEST FAILED")
        print(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
