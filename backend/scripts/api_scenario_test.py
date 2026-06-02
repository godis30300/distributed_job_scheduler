from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api").rstrip("/")
USERNAME = f"api_scenario_{int(time.time())}"
PASSWORD = "scenario123"


def step(message: str) -> None:
    print(f"[api-scenario] {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def request_json(client: httpx.Client, method: str, path: str, **kwargs) -> Any:
    response = client.request(method, f"{API_BASE_URL}{path}", timeout=15, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed: HTTP {response.status_code} {response.text[:500]}")
    if not response.content:
        return {}
    return response.json()


def wait_for_terminal_run(client: httpx.Client, run_id: str, token: str, seconds: int = 20) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + seconds
    while time.time() < deadline:
        run = request_json(client, "GET", f"/job-runs/{run_id}", headers=headers)
        if run["status"] in {"success", "failed", "timeout", "canceled"}:
            return run
        time.sleep(1)
    raise TimeoutError(f"run did not finish in {seconds}s: {run_id}")


def create_job(client: httpx.Client, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return request_json(client, "POST", "/jobs", headers={"Authorization": f"Bearer {token}"}, json=payload)


def trigger_job(client: httpx.Client, token: str, job_id: str) -> str:
    response = request_json(client, "POST", f"/jobs/{job_id}/run", headers={"Authorization": f"Bearer {token}"})
    return response["run_id"]


def main() -> int:
    try:
        with httpx.Client() as client:
            step("checking health aliases")
            health = request_json(client, "GET", "/health")
            system_health = request_json(client, "GET", "/system/health")
            require(health["status"] == "healthy", "/api/health should be healthy")
            require(system_health["status"] == "healthy", "/api/system/health should be healthy")

            step("registering and logging in a real user")
            request_json(
                client,
                "POST",
                "/auth/register",
                json={"username": USERNAME, "email": f"{USERNAME}@example.com", "password": PASSWORD, "role": "operator"},
            )
            login = request_json(client, "POST", "/auth/login", json={"username": USERNAME, "password": PASSWORD})
            token = login["access_token"]
            auth_headers = {"Authorization": f"Bearer {token}"}
            me = request_json(client, "GET", "/auth/me", headers=auth_headers)
            require(me["username"] == USERNAME, "/auth/me should return the logged-in user")

            suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

            step("creating and running new-format shell job")
            shell_job = create_job(
                client,
                token,
                {
                    "name": f"scenario-shell-{suffix}",
                    "task_type": "shell",
                    "script": f"echo scenario-shell-{suffix}",
                    "description": "new-format shell scenario",
                    "working_dir": f"scenario-shell-{suffix}",
                    "schedule_type": "manual",
                    "timeout_seconds": 30,
                    "retry_limit": 1,
                    "status": "enabled",
                },
            )
            require(shell_job["name"] == f"scenario-shell-{suffix}", "shell job name should be returned")
            require(shell_job["task_type"] == "shell", "shell job task_type should be returned")
            shell_run = wait_for_terminal_run(client, trigger_job(client, token, shell_job["id"]), token)
            require(shell_run["status"] == "success", "shell run should succeed")
            require(shell_run["duration_seconds_decimal"] > 0, "shell run should have decimal duration")
            require("scenario-shell" in (shell_run["stdout"] or ""), "shell stdout should be saved")
            shell_logs = request_json(client, "GET", f"/job-runs/{shell_run['id']}/logs", headers=auth_headers)
            require(shell_logs, "shell run logs should be queryable")

            step("creating and running new-format python job")
            python_job = create_job(
                client,
                token,
                {
                    "name": f"scenario-python-{suffix}",
                    "task_type": "python",
                    "script": f"print('scenario-python-{suffix}')",
                    "description": "new-format python scenario",
                    "working_dir": f"scenario-python-{suffix}",
                    "schedule_type": "manual",
                    "timeout_seconds": 30,
                    "retry_limit": 1,
                    "status": "enabled",
                },
            )
            python_run = wait_for_terminal_run(client, trigger_job(client, token, python_job["id"]), token)
            require(python_run["status"] == "success", "python run should succeed")
            require(python_run["duration_seconds_decimal"] > 0, "python run should have decimal duration")
            require("scenario-python" in (python_run["stdout"] or ""), "python stdout should be saved")

            step("checking old-format job payload compatibility")
            legacy_job = create_job(
                client,
                token,
                {
                    "task_name": f"scenario-legacy-{suffix}",
                    "schedule_type": "manual",
                    "action": "shell",
                    "action_payload": {"script": f"echo scenario-legacy-{suffix}", "args": []},
                    "timeout_seconds": 30,
                    "max_retry": 1,
                    "status": "enabled",
                },
            )
            legacy_run = wait_for_terminal_run(client, trigger_job(client, token, legacy_job["id"]), token)
            require(legacy_run["status"] == "success", "legacy run should succeed")
            require(legacy_run["duration_seconds_decimal"] > 0, "legacy run should have decimal duration")

            step("checking failed run and retry API")
            fail_job = create_job(
                client,
                token,
                {
                    "task_name": f"scenario-fail-{suffix}",
                    "schedule_type": "manual",
                    "action": "fail-test",
                    "action_payload": {},
                    "timeout_seconds": 30,
                    "max_retry": 1,
                    "status": "enabled",
                },
            )
            failed_run = wait_for_terminal_run(client, trigger_job(client, token, fail_job["id"]), token)
            require(failed_run["status"] == "failed", "fail-test run should fail")
            retry_run = request_json(client, "POST", f"/job-runs/{failed_run['id']}/retry", headers=auth_headers)
            require(retry_run["status"] == "pending", "retry should create a pending run")
            require(retry_run["retry_count"] == failed_run["retry_count"] + 1, "retry_count should increment")

            step("checking list/search/dashboard/metrics endpoints")
            runs = request_json(client, "GET", "/job-runs?limit=100&offset=0", headers=auth_headers)
            require(any(run["id"] == shell_run["id"] for run in runs), "list job-runs should include shell run")
            search_logs = request_json(client, "GET", f"/job-runs/logs/search?task_name={shell_job['task_name']}", headers=auth_headers)
            require(search_logs, "log search should return shell logs")
            summary = request_json(client, "GET", "/dashboard/summary", headers=auth_headers)
            require("total_jobs" in summary and "total_runs_today" in summary, "dashboard summary should include job/run counts")
            metrics = client.get(f"{API_BASE_URL}/metrics", timeout=15).text
            for metric_name in (
                "scheduler_job_runs_total",
                "scheduler_queue_length",
                "scheduler_worker_load",
                "scheduler_container_memory_usage_bytes",
                "scheduler_container_cpu_usage_seconds_total",
                "scheduler_pod_restart_count",
            ):
                require(metric_name in metrics, f"missing metric: {metric_name}")

        print("\nAPI SCENARIO TEST PASSED")
        return 0
    except Exception as exc:
        print("\nAPI SCENARIO TEST FAILED")
        print(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
