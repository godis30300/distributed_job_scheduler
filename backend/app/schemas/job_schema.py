from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobBase(BaseModel):
    task_name: str = Field(min_length=1, max_length=120)
    action_type: str = Field(pattern="^(api_call|shell)$")
    action_payload: dict[str, Any]
    schedule_rule: str = Field(min_length=3, max_length=120)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    max_retry: int = Field(default=3, ge=0, le=10)
    enabled: bool = True
    description: str | None = None


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    task_name: str | None = None
    action_type: str | None = Field(default=None, pattern="^(api_call|shell)$")
    action_payload: dict[str, Any] | None = None
    schedule_rule: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    max_retry: int | None = Field(default=None, ge=0, le=10)
    enabled: bool | None = None
    description: str | None = None


class JobResponse(JobBase):
    id: str
    created_by: str | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TriggerResponse(BaseModel):
    run_id: str
    status: str
