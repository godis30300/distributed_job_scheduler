from datetime import datetime, timezone

import pytest

from app.services.schedule_utils import compute_next_run


def test_compute_next_run_supports_every_seconds() -> None:
    base_time = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)

    next_run = compute_next_run("every:30s", base_time)

    assert next_run == datetime(2026, 6, 3, 12, 0, 30, tzinfo=timezone.utc)


def test_compute_next_run_supports_cron() -> None:
    base_time = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)

    next_run = compute_next_run("*/5 * * * *", base_time)

    assert next_run == datetime(2026, 6, 3, 12, 5, 0, tzinfo=timezone.utc)


def test_compute_next_run_rejects_unknown_every_suffix() -> None:
    with pytest.raises(ValueError, match="Unsupported every format"):
        compute_next_run("every:2d")
