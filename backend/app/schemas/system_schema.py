from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    api: str
    worker_hint: str


class DashboardSummary(BaseModel):
    total_jobs: int
    enabled_jobs: int
    pending_runs: int
    running_runs: int
    success_today: int
    failed_today: int
    total_runs_today: int
    worker_count_hint: int
