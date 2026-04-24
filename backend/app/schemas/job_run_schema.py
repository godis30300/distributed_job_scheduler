from datetime import datetime

from pydantic import BaseModel


class JobRunResponse(BaseModel):
    id: str
    job_id: str
    status: str
    triggered_by: str | None
    trigger_type: str
    worker_id: str | None
    start_time: datetime | None
    end_time: datetime | None
    heartbeat_at: datetime | None
    duration_seconds: int | None
    retry_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobLogResponse(BaseModel):
    id: str
    job_run_id: str
    log_level: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusUpdateRequest(BaseModel):
    status: str
    error_message: str | None = None
