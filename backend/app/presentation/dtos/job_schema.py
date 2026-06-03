from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

NAME_PATTERN = r'^[a-zA-Z0-9_-]+$'

class JobBase(BaseModel):
    task_name: str = Field(..., pattern=NAME_PATTERN)
    name: Optional[str] = None
    description: Optional[str] = None
    status: str = "enabled"
    schedule_type: str = "manual"
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    action: str = "api_call"
    task_type: Optional[str] = None
    
    # API Call parameters
    api_method: str = "GET"
    api_url: Optional[str] = None
    
    # Script parameters
    working_dir: Optional[str] = None
    shell_script: Optional[str] = None
    script_content: Optional[str] = None
    script: Optional[str] = None
    
    action_payload: dict[str, Any] = Field(default_factory=dict)
    
    timeout_seconds: int = 300
    retry_limit: int = 3

    @model_validator(mode="before")
    @classmethod
    def sync_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        # Handle 'name' vs 'task_name'
        if "name" in normalized and "task_name" not in normalized:
            normalized["task_name"] = normalized["name"]
        # Handle 'action_type' vs 'action'
        if "action_type" in normalized and "action" not in normalized:
            normalized["action"] = normalized["action_type"]
        return normalized

class JobCreate(JobBase):
    depends_on: Optional[list[str]] = None

class JobUpdate(BaseModel):
    task_name: Optional[str] = Field(None, pattern=NAME_PATTERN)
    description: Optional[str] = None
    status: Optional[str] = None
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    action: Optional[str] = None
    api_method: Optional[str] = None
    api_url: Optional[str] = None
    working_dir: Optional[str] = None
    shell_script: Optional[str] = None
    script_content: Optional[str] = None
    timeout_seconds: Optional[int] = None
    retry_limit: Optional[int] = None

class JobResponse(BaseModel):
    id: str
    user: str
    created_by: Optional[str] = None
    task_name: Optional[str] = None
    action_type: Optional[str] = None
    action_payload: dict[str, Any]
    status: str = "enabled"
    enabled: bool = True
    description: Optional[str] = None
    schedule_rule: str
    max_retry: int
    timeout_seconds: int
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def normalize_for_response(cls, data: Any) -> Any:
        # This validator ensures that the backend Model fields are correctly mapped to Response fields
        if hasattr(data, "id"): # It's a SQLAlchemy model
            normalized = {
                "id": str(data.id),
                "user": getattr(data.user, "username", "unknown") if hasattr(data, "user") else "unknown",
                "created_by": getattr(data.user, "username", "unknown") if hasattr(data, "user") else "unknown",
                "task_name": data.task_name,
                "action_type": data.action_type,
                "action_payload": data.action_payload,
                "status": data.status,
                "enabled": data.enabled,
                "description": data.description,
                "schedule_rule": data.schedule_rule,
                "max_retry": data.max_retry,
                "timeout_seconds": data.timeout_seconds,
                "next_run_at": data.next_run_at,
                "last_run_at": data.last_run_at,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
            return normalized
        return data

class TriggerResponse(BaseModel):
    run_id: str
    status: str
