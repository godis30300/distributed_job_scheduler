import asyncio
import json
import pathlib
from typing import Any

import httpx

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"
DEFAULT_WORK_DIR = pathlib.Path("/tmp/job-scheduler-work")


class ExecutionResult(dict):
    pass


async def execute_api_call(payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    method = payload.get("method", "GET").upper()
    url = payload.get("url")
    headers = payload.get("headers") or {}
    body = payload.get("body")

    if not url:
        return ExecutionResult(success=False, stdout="", stderr="missing url")

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.request(method, url, headers=headers, json=body)
        return ExecutionResult(
            success=response.status_code < 400,
            stdout=response.text[:5000],
            stderr="" if response.status_code < 400 else f"HTTP {response.status_code}",
        )


async def execute_shell(payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    script = payload.get("content") or payload.get("script")
    command = payload.get("command")
    args = payload.get("args") or []

    if not script and not command:
        return ExecutionResult(success=False, stdout="", stderr="missing script")

    working_dir = _resolve_working_dir(payload.get("working_dir"))
    if working_dir is None:
        return ExecutionResult(success=False, stdout="", stderr="invalid working_dir")

    if command:
        executable = ("bash", "-lc", str(command))
    else:
        script_text = str(script)
        script_path = (SCRIPTS_DIR / script_text).resolve()
        if "\n" not in script_text and SCRIPTS_DIR in script_path.parents and script_path.exists():
            executable = ("bash", str(script_path), *[str(arg) for arg in args])
        else:
            executable = ("bash", "-lc", script_text)

    process = await asyncio.create_subprocess_exec(
        *executable,
        cwd=str(working_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        process.kill()
        return ExecutionResult(success=False, stdout="", stderr=f"timeout after {timeout_seconds}s")

    return ExecutionResult(
        success=process.returncode == 0,
        stdout=stdout.decode(errors="replace")[:5000],
        stderr=stderr.decode(errors="replace")[:5000],
    )


async def execute_python(payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    script = payload.get("content") or payload.get("script")
    if not script:
        return ExecutionResult(success=False, stdout="", stderr="missing python script")

    working_dir = _resolve_working_dir(payload.get("working_dir"))
    if working_dir is None:
        return ExecutionResult(success=False, stdout="", stderr="invalid working_dir")

    process = await asyncio.create_subprocess_exec(
        "python",
        "-c",
        str(script),
        cwd=str(working_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        process.kill()
        return ExecutionResult(success=False, stdout="", stderr=f"timeout after {timeout_seconds}s")

    return ExecutionResult(
        success=process.returncode == 0,
        stdout=stdout.decode(errors="replace")[:5000],
        stderr=stderr.decode(errors="replace")[:5000],
    )


def _resolve_working_dir(raw_working_dir: str | None) -> pathlib.Path | None:
    if not raw_working_dir:
        DEFAULT_WORK_DIR.mkdir(parents=True, exist_ok=True)
        return DEFAULT_WORK_DIR

    path = pathlib.Path(raw_working_dir)
    if not path.is_absolute():
        path = DEFAULT_WORK_DIR / path
    path = path.resolve()

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return path


async def execute_job(action_type: str, payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    if action_type == "api_call":
        return await execute_api_call(payload, timeout_seconds)
    if action_type == "shell":
        return await execute_shell(payload, timeout_seconds)
    if action_type == "python":
        return await execute_python(payload, timeout_seconds)
    if action_type == "report":
        return ExecutionResult(success=True, stdout="daily report generated", stderr="")
    if action_type == "email":
        return ExecutionResult(success=True, stdout="email sent", stderr="")
    if action_type == "backup":
        return ExecutionResult(success=True, stdout="database backup completed", stderr="")
    if action_type == "fail-test":
        return ExecutionResult(success=False, stdout="", stderr="intentional failure for retry test")
    if action_type == "long-task":
        await asyncio.sleep(min(timeout_seconds, 2))
        return ExecutionResult(success=True, stdout="long task completed", stderr="")
    return ExecutionResult(success=False, stdout="", stderr=f"unsupported action_type: {action_type}")
