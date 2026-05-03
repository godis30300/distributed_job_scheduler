from datetime import datetime

from pydantic import BaseModel


class JobRunResponse(BaseModel):
    id: str
    job_id: str
    status: str
    triggered_by: str | None
    trigger_type: str
    worker_id: str | None
    locked_by: str | None
    locked_until: datetime | None
    start_time: datetime | None
    end_time: datetime | None
    heartbeat_at: datetime | None
    duration_seconds: int | None
    retry_count: int
    stdout: str | None
    stderr: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobLogResponse(BaseModel):
    id: str
    job_run_id: str
    log_level: str
    stream: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusUpdateRequest(BaseModel):
    status: str
    stdout: str | None = None
    stderr: str | None = None
    error_message: str | None = None
