from datetime import datetime, timedelta, timezone

from croniter import croniter


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
