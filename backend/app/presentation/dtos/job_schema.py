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
        if "task_type" in normalized and "action" not in normalized:
            normalized["action"] = normalized["task_type"]
        
        # Normalize action names
        if normalized.get("action") == "python_script":
            normalized["action"] = "python"
        if normalized.get("task_type") == "python_script":
            normalized["task_type"] = "python"

        # Handle 'max_retry' vs 'retry_limit'
        if "max_retry" in normalized and "retry_limit" not in normalized:
            normalized["retry_limit"] = normalized["max_retry"]
        
        # Handle script fields
        if "script_content" in normalized and "script" not in normalized:
            normalized["script"] = normalized["script_content"]
        if "shell_script" in normalized and "script" not in normalized:
            normalized["script"] = normalized["shell_script"]

        # Handle 'schedule_rule' to DDD fields
        if "schedule_rule" in normalized:
            rule = normalized["schedule_rule"]
            if rule == "manual":
                normalized["schedule_type"] = "manual"
            elif rule.startswith("cron:"):
                normalized["schedule_type"] = "cron"
                normalized["cron_expression"] = rule[5:]
            elif rule.startswith("every:"):
                normalized["schedule_type"] = "interval"
                val = rule[6:]
                if val.endswith("s"): val = val[:-1]
                normalized["interval_seconds"] = int(val)
            else:
                # Default to manual if unrecognized
                normalized["schedule_type"] = normalized.get("schedule_type", "manual")
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
    task_type: Optional[str] = None
    api_method: Optional[str] = None
    api_url: Optional[str] = None
    working_dir: Optional[str] = None
    shell_script: Optional[str] = None
    script_content: Optional[str] = None
    script: Optional[str] = None
    action_payload: Optional[dict[str, Any]] = None
    timeout_seconds: Optional[int] = None
    retry_limit: Optional[int] = None
    depends_on: Optional[list[str]] = None

class JobResponse(BaseModel):
    id: str
    user: str
    created_by: Optional[str] = None
    name: Optional[str] = None
    task_name: Optional[str] = None
    task_type: Optional[str] = None
    action: Optional[str] = None
    action_type: Optional[str] = None
    action_payload: dict[str, Any]
    status: str = "enabled"
    enabled: bool = True
    description: Optional[str] = None
    schedule_rule: str
    schedule_type: str
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    max_retry: int
    retry_limit: int
    timeout_seconds: int
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    depends_on: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def normalize_for_response(cls, data: Any) -> Any:
        # This validator ensures that the backend Model fields are correctly mapped to Response fields
        if hasattr(data, "id"): # It's a SQLAlchemy model
            # For depends_on, we want task_names
            depends_on = []
            if hasattr(data, "id"):
                # We need a way to get dependency names. 
                # For now, let's just use the job_id if we don't have a better way.
                # Actually, Job entity might have a relationship.
                pass

            normalized = {
                "id": str(data.id),
                "user": getattr(data.user, "username", "unknown") if hasattr(data, "user") else "unknown",
                "created_by": getattr(data.user, "username", "unknown") if hasattr(data, "user") else "unknown",
                "name": data.name,
                "task_name": data.task_name,
                "task_type": data.task_type,
                "action": data.action_type,
                "action_type": data.action_type,
                "action_payload": data.action_payload,
                "status": data.status,
                "enabled": data.enabled,
                "description": data.description,
                "schedule_rule": data.schedule_rule,
                "schedule_type": data.schedule_type,
                "cron_expression": data.cron_expression,
                "interval_seconds": data.interval_seconds,
                "max_retry": data.max_retry,
                "retry_limit": data.max_retry,
                "timeout_seconds": data.timeout_seconds,
                "next_run_at": data.next_run_at,
                "last_run_at": data.last_run_at,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
                "depends_on": getattr(data, "depends_on_names", []),
            }
            return normalized
        return data

class TriggerResponse(BaseModel):
    run_id: str
    status: str
