from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


ACTION_PATTERN = "^(api_call|shell|report|email|backup|fail-test|long-task)$"
SCHEDULE_PATTERN = "^(manual|cron|interval)$"
STATUS_PATTERN = "^(enabled|disabled|active|paused|deleted)$"


class JobBase(BaseModel):
    task_name: str = Field(min_length=1, max_length=120)
    status: str = Field(default="enabled", pattern=STATUS_PATTERN)
    schedule_type: str = Field(default="manual", pattern=SCHEDULE_PATTERN)
    cron_expression: str | None = None
    interval_seconds: int | None = Field(default=None, ge=1)
    action: str = Field(pattern=ACTION_PATTERN)
    action_payload: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    retry_limit: int = Field(default=3, ge=0, le=10)
    enabled: bool | None = None
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_api_fields(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "action" not in normalized and "action_type" in normalized:
            normalized["action"] = normalized["action_type"]
        if "retry_limit" not in normalized and "max_retry" in normalized:
            normalized["retry_limit"] = normalized["max_retry"]
        if "schedule_rule" in normalized and "schedule_type" not in normalized:
            rule = str(normalized["schedule_rule"])
            if rule == "manual":
                normalized["schedule_type"] = "manual"
            elif rule.startswith("every:"):
                normalized["schedule_type"] = "interval"
                value = rule.split(":", 1)[1].strip()
                if value.endswith("s"):
                    normalized["interval_seconds"] = int(value[:-1])
                elif value.endswith("m"):
                    normalized["interval_seconds"] = int(value[:-1]) * 60
                elif value.endswith("h"):
                    normalized["interval_seconds"] = int(value[:-1]) * 3600
            else:
                normalized["schedule_type"] = "cron"
                normalized["cron_expression"] = rule
        return normalized

    @model_validator(mode="after")
    def validate_schedule_fields(self):
        if self.schedule_type == "cron" and not self.cron_expression:
            raise ValueError("cron_expression is required when schedule_type is cron")
        if self.schedule_type == "interval" and not self.interval_seconds:
            raise ValueError("interval_seconds is required when schedule_type is interval")
        return self


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    task_name: str | None = None
    status: str | None = Field(default=None, pattern=STATUS_PATTERN)
    schedule_type: str | None = Field(default=None, pattern=SCHEDULE_PATTERN)
    cron_expression: str | None = None
    interval_seconds: int | None = Field(default=None, ge=1)
    action: str | None = Field(default=None, pattern=ACTION_PATTERN)
    action_payload: dict[str, Any] | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    retry_limit: int | None = Field(default=None, ge=0, le=10)
    enabled: bool | None = None
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_api_fields(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "action" not in normalized and "action_type" in normalized:
            normalized["action"] = normalized["action_type"]
        if "retry_limit" not in normalized and "max_retry" in normalized:
            normalized["retry_limit"] = normalized["max_retry"]
        if "schedule_rule" in normalized and "schedule_type" not in normalized:
            rule = str(normalized["schedule_rule"])
            if rule == "manual":
                normalized["schedule_type"] = "manual"
            elif rule.startswith("every:"):
                normalized["schedule_type"] = "interval"
                value = rule.split(":", 1)[1].strip()
                if value.endswith("s"):
                    normalized["interval_seconds"] = int(value[:-1])
                elif value.endswith("m"):
                    normalized["interval_seconds"] = int(value[:-1]) * 60
                elif value.endswith("h"):
                    normalized["interval_seconds"] = int(value[:-1]) * 3600
            else:
                normalized["schedule_type"] = "cron"
                normalized["cron_expression"] = rule
        return normalized


class JobResponse(JobBase):
    id: str
    user: str
    created_by: str | None
    action_type: str
    action_payload: dict[str, Any]
    schedule_rule: str
    max_retry: int
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TriggerResponse(BaseModel):
    run_id: str
    status: str
