import asyncio
import os
import pathlib
import tempfile
from typing import Any

import httpx

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[3] / "scripts"
DEFAULT_WORK_DIR = pathlib.Path(".job-scheduler-work").resolve()


class ExecutionResult(dict):
    pass


def _execution_env(payload: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env["RETRY_COUNT"] = str(payload.get("retry_count", 0))
    return env


def _write_temp_script(working_dir: pathlib.Path, suffix: str, content: str) -> pathlib.Path:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix, dir=working_dir, delete=False) as handle:
        handle.write(content)
        handle.write("\n")
        return pathlib.Path(handle.name)


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
        if not isinstance(command, list) or not command:
            return ExecutionResult(success=False, stdout="", stderr="command must be a non-empty list")
        executable = tuple(str(part) for part in command)
    else:
        script_text = str(script)
        script_path = (SCRIPTS_DIR / script_text).resolve()
        if "\n" not in script_text and SCRIPTS_DIR in script_path.parents and script_path.exists():
            executable = ("bash", str(script_path), *[str(arg) for arg in args])
        else:
            script_file = _write_temp_script(working_dir, ".sh", script_text)
            executable = ("bash", str(script_file))

    process = await asyncio.create_subprocess_exec(  # NOSONAR: isolated worker executes explicitly submitted job scripts.
        *executable,
        cwd=str(working_dir),
        env=_execution_env(payload),
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

    script_file = _write_temp_script(working_dir, ".py", str(script))

    process = await asyncio.create_subprocess_exec(  # NOSONAR: isolated worker executes explicitly submitted job scripts.
        "python",
        str(script_file),
        cwd=str(working_dir),
        env=_execution_env(payload),
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
    if path.is_absolute() or ".." in path.parts:
        return None
    path = DEFAULT_WORK_DIR / path
    path = path.resolve()

    if DEFAULT_WORK_DIR.resolve() not in (path, *path.parents):
        return None

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return path


async def execute_api_poll(payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    trigger_url = payload.get("trigger_url") or payload.get("url")
    method = payload.get("method", "POST").upper()
    headers = payload.get("headers") or {}
    body = payload.get("body")

    if not trigger_url:
        return ExecutionResult(success=False, stdout="", stderr="missing trigger_url")

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        try:
            response = await client.request(method, trigger_url, headers=headers, json=body)
            if response.status_code >= 400:
                return ExecutionResult(success=False, stdout="", stderr=f"HTTP {response.status_code}: {response.text}")
            
            data = response.json()
            external_id = data.get("job_id") or data.get("id") or data.get("external_id")
            
            if not external_id:
                return ExecutionResult(success=False, stdout="", stderr="API did not return a job_id")

            return ExecutionResult(
                success=True,
                status="awaiting",
                external_id=external_id,
                stdout=f"Job triggered. External ID: {external_id}",
                stderr=""
            )
        except Exception as e:
            return ExecutionResult(success=False, stdout="", stderr=str(e))


async def execute_job(action_type: str, payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    def exec_report(*args):
        return ExecutionResult(success=True, stdout="daily report generated", stderr="")

    def exec_email(*args):
        return ExecutionResult(success=True, stdout="email sent", stderr="")

    def exec_backup(*args):
        return ExecutionResult(success=True, stdout="database backup completed", stderr="")

    def exec_fail_test(*args):
        return ExecutionResult(success=False, stdout="", stderr="intentional failure for retry test")

    async def exec_long_task(*args):
        await asyncio.sleep(min(timeout_seconds, 2))
        return ExecutionResult(success=True, stdout="long task completed", stderr="")

    action_map = {
        "api_call": execute_api_call,
        "api_poll": execute_api_poll,
        "shell": execute_shell,
        "python": execute_python,
        "report": exec_report,
        "email": exec_email,
        "backup": exec_backup,
        "fail-test": exec_fail_test,
        "long-task": exec_long_task,
    }

    executor = action_map.get(action_type)
    if executor:
        # Check if it is a coroutine function or a regular function
        if asyncio.iscoroutinefunction(executor):
            return await executor(payload, timeout_seconds)
        return executor(payload, timeout_seconds)
    
    return ExecutionResult(success=False, stdout="", stderr=f"unsupported action_type: {action_type}")
