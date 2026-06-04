import os
from pathlib import Path

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.database.database import get_db
from app.domain.entities.job_run import JobRun

router = APIRouter(tags=["metrics"])

api_requests_total = Counter("scheduler_api_requests_total", "Total API requests")
worker_load = Gauge("scheduler_worker_load", "Worker load hint")
queue_length = Gauge("scheduler_queue_length", "Queue length hint")
job_runs_by_status = Gauge("scheduler_job_runs_total", "Job run count by status", ["status"])
container_memory_usage_bytes = Gauge("scheduler_container_memory_usage_bytes", "Container memory usage from cgroup")
container_cpu_usage_seconds = Gauge("scheduler_container_cpu_usage_seconds_total", "Container CPU usage from cgroup")
pod_restart_count = Gauge("scheduler_pod_restart_count", "Pod restart count hint from POD_RESTART_COUNT env")


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    api_requests_total.inc()
    _update_job_metrics(db)
    _update_container_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _update_job_metrics(db: Session) -> None:
    counts = dict(db.query(JobRun.status, func.count(JobRun.id)).group_by(JobRun.status).all())
    for status in ("pending", "running", "success", "failed", "timeout", "canceled"):
        job_runs_by_status.labels(status=status).set(counts.get(status, 0))
    queue_length.set(counts.get("pending", 0))
    worker_load.set(counts.get("running", 0))


def _update_container_metrics() -> None:
    memory = _read_int("/sys/fs/cgroup/memory.current") or _read_int("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    if memory is not None:
        container_memory_usage_bytes.set(memory)

    cpu_usec = _read_cpu_usec()
    if cpu_usec is not None:
        container_cpu_usage_seconds.set(cpu_usec / 1_000_000)

    pod_restart_count.set(float(os.getenv("POD_RESTART_COUNT", "0")))


def _read_int(path: str) -> int | None:
    try:
        return int(Path(path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _read_cpu_usec() -> int | None:
    cpu_stat = Path("/sys/fs/cgroup/cpu.stat")
    try:
        for line in cpu_stat.read_text(encoding="utf-8").splitlines():
            key, value = line.split(maxsplit=1)
            if key == "usage_usec":
                return int(value)
    except (OSError, ValueError):
        return None
    return None
