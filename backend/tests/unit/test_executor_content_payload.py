import pytest

from app.application.services.executor import execute_job


@pytest.mark.asyncio
async def test_python_executor_prefers_content_over_script_name():
    result = await execute_job(
        "python",
        {
            "script": "ui-job-name",
            "content": 'print("hello from content")',
            "working_dir": "executor-content-test",
        },
        30,
    )

    assert result["success"] is True
    assert "hello from content" in result["stdout"]


@pytest.mark.asyncio
async def test_shell_executor_prefers_content_over_script_name():
    result = await execute_job(
        "shell",
        {
            "script": "ui-job-name",
            "content": 'echo "hello from shell content"',
            "working_dir": "executor-content-test",
        },
        30,
    )

    assert result["success"] is True
    assert "hello from shell content" in result["stdout"]
