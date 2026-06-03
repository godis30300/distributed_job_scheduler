from datetime import datetime, timedelta, timezone
from typing import Any
from croniter import croniter


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def resolve_schedule_rule(payload: Any, current_rule: str | None = None) -> str:
    """
    Business logic to determine the canonical schedule string from DTO or dict.
    """
    # Use getattr if it's an object, else use .get if it's a dict
    def get_val(key, default=None):
        if hasattr(payload, key):
            return getattr(payload, key)
        if isinstance(payload, dict):
            return payload.get(key, default)
        return default

    stype = get_val("schedule_type")
    if not stype:
        return current_rule or "manual"
    
    if stype == "manual":
        return "manual"
    if stype == "cron":
        return get_val("cron_expression") or ""
    if stype == "interval":
        seconds = get_val("interval_seconds")
        return f"every:{seconds}s"
    return current_rule or "manual"


def compute_next_run(schedule_rule: str, base_time: datetime | None = None) -> datetime:
    base = base_time or utcnow()
    rule = schedule_rule.strip()

    if rule.startswith("every:"):
        value = rule.split(":", 1)[1].strip()
        if value.endswith("m"):
            return base + timedelta(minutes=int(value[:-1]))
        if value.endswith("h"):
            return base + timedelta(hours=int(value[:-1]))
        if value.endswith("s"):
            return base + timedelta(seconds=int(value[:-1]))
        raise ValueError("Unsupported every format. Use every:5m, every:1h, or every:30s")

    if croniter.is_valid(rule):
        return croniter(rule, base).get_next(datetime)

    raise ValueError("Unsupported schedule_rule. Use every:5m or cron expression like 0 2 * * *")
