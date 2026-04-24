import asyncio
import json
import pathlib
from typing import Any

import httpx

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"


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
    script = payload.get("script")
    args = payload.get("args") or []

    if not script:
        return ExecutionResult(success=False, stdout="", stderr="missing script")

    script_path = (SCRIPTS_DIR / script).resolve()
    if SCRIPTS_DIR not in script_path.parents:
        return ExecutionResult(success=False, stdout="", stderr="invalid script path")
    if not script_path.exists():
        return ExecutionResult(success=False, stdout="", stderr=f"script not found: {script}")

    process = await asyncio.create_subprocess_exec(
        "bash",
        str(script_path),
        *[str(arg) for arg in args],
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


async def execute_job(action_type: str, payload: dict[str, Any], timeout_seconds: int) -> ExecutionResult:
    if action_type == "api_call":
        return await execute_api_call(payload, timeout_seconds)
    if action_type == "shell":
        return await execute_shell(payload, timeout_seconds)
    if action_type == "backup":
        # Demo placeholder. Replace with real backup logic.
        await asyncio.sleep(1)
        return ExecutionResult(success=True, stdout="backup placeholder finished", stderr="")
    return ExecutionResult(success=False, stdout="", stderr=f"unsupported action_type: {action_type}")
