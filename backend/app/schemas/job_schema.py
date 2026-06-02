from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


ACTION_PATTERN = "^(api_call|shell|python|report|email|backup|fail-test|long-task)$"
SCHEDULE_PATTERN = "^(manual|cron|interval)$"
STATUS_PATTERN = "^(enabled|disabled|active|paused|deleted)$"


class JobBase(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    task_name: str | None = Field(default=None, min_length=1, max_length=120)
    task_type: str | None = Field(default=None, pattern=ACTION_PATTERN)
    script: str | None = None
    working_dir: str | None = None
    status: str = Field(default="enabled", pattern=STATUS_PATTERN)
    schedule_type: str = Field(default="manual", pattern=SCHEDULE_PATTERN)
    cron_expression: str | None = None
    interval_seconds: int | None = Field(default=None, ge=1)
    action: str | None = Field(default=None, pattern=ACTION_PATTERN)
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
        if "task_name" not in normalized and "name" in normalized:
            normalized["task_name"] = normalized["name"]
        if "name" not in normalized and "task_name" in normalized:
            normalized["name"] = normalized["task_name"]
        if "action" not in normalized and "task_type" in normalized:
            normalized["action"] = normalized["task_type"]
        if "task_type" not in normalized and "action" in normalized:
            normalized["task_type"] = normalized["action"]
        if "action" not in normalized and "action_type" in normalized:
            normalized["action"] = normalized["action_type"]
        if "task_type" not in normalized and "action_type" in normalized:
            normalized["task_type"] = normalized["action_type"]
        if "retry_limit" not in normalized and "max_retry" in normalized:
            normalized["retry_limit"] = normalized["max_retry"]
        if "action_payload" not in normalized:
            payload = {}
            if "script" in normalized and normalized["script"] is not None:
                payload["script"] = normalized["script"]
            if "working_dir" in normalized and normalized["working_dir"] is not None:
                payload["working_dir"] = normalized["working_dir"]
            if payload:
                normalized["action_payload"] = payload
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
        if not self.task_name:
            raise ValueError("task_name or name is required")
        if not self.action:
            raise ValueError("action or task_type is required")
        if self.schedule_type == "cron" and not self.cron_expression:
            raise ValueError("cron_expression is required when schedule_type is cron")
        if self.schedule_type == "interval" and not self.interval_seconds:
            raise ValueError("interval_seconds is required when schedule_type is interval")
        return self


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    name: str | None = None
    task_name: str | None = None
    task_type: str | None = Field(default=None, pattern=ACTION_PATTERN)
    script: str | None = None
    working_dir: str | None = None
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
        if "task_name" not in normalized and "name" in normalized:
            normalized["task_name"] = normalized["name"]
        if "name" not in normalized and "task_name" in normalized:
            normalized["name"] = normalized["task_name"]
        if "action" not in normalized and "task_type" in normalized:
            normalized["action"] = normalized["task_type"]
        if "task_type" not in normalized and "action" in normalized:
            normalized["task_type"] = normalized["action"]
        if "action" not in normalized and "action_type" in normalized:
            normalized["action"] = normalized["action_type"]
        if "task_type" not in normalized and "action_type" in normalized:
            normalized["task_type"] = normalized["action_type"]
        if "retry_limit" not in normalized and "max_retry" in normalized:
            normalized["retry_limit"] = normalized["max_retry"]
        if any(key in normalized for key in ("script", "working_dir")):
            payload = dict(normalized.get("action_payload") or {})
            if "script" in normalized:
                payload["script"] = normalized["script"]
            if "working_dir" in normalized:
                payload["working_dir"] = normalized["working_dir"]
            normalized["action_payload"] = payload
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
