from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain.entities.job import Job
from app.domain.entities.job_dependency import JobDependency
from app.domain.entities.job_run import JobRun
from app.domain.entities.user import User
from app.presentation.dtos.job_schema import JobCreate, JobUpdate
from app.services.schedule_utils import resolve_schedule_rule


ACTIVE_JOB_STATUSES = ("enabled", "active")


def _is_admin(user: User | None) -> bool:
    return bool(user and user.role == "admin")


def _job_query_for_user(db: Session, current_user: User | None):
    query = db.query(Job)
    if current_user and not _is_admin(current_user):
        query = query.filter(Job.user_id == current_user.id)
    return query


def _ensure_job_access(job: Job, current_user: User | None) -> Job:
    if current_user and not _is_admin(current_user) and job.user_id and job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def create_job(db: Session, payload: JobCreate, current_user: User) -> Job:
    from app.application.services.job_service import JobService
    service = JobService(db)
    try:
        return service.create_job(payload, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


def list_jobs(
    db: Session,
    current_user: User | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> list[Job]:
    query = _job_query_for_user(db, current_user)

    if status == "enabled":
        query = query.filter(Job.enabled.is_(True))
    elif status == "disabled":
        query = query.filter(Job.enabled.is_(False))
    elif status == "active":
        query = query.filter(Job.status.in_(ACTIVE_JOB_STATUSES))
    elif status:
        query = query.filter(Job.status == status)
        
    if keyword:
        query = query.filter(Job.task_name.ilike(f"%{keyword}%"))
        
    return query.order_by(Job.created_at.desc()).all()


def get_job_or_404(db: Session, job_id: str, current_user: User | None = None) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _ensure_job_access(job, current_user)


def _apply_field_aliases(job: Job, data: dict) -> None:
    aliases = {
        "action": "action_type",
        "task_type": "task_type",
        "retry_limit": "max_retry",
    }
    for source, target in aliases.items():
        if source in data:
            setattr(job, target, data[source])


def _apply_direct_fields(job: Job, data: dict) -> None:
    direct_fields = (
        "name",
        "task_name",
        "script",
        "working_dir",
        "status",
        "timeout_seconds",
        "description",
    )
    for field in direct_fields:
        if field in data:
            setattr(job, field, data[field])


def _payload_needs_rebuild(data: dict) -> bool:
    payload_fields = ("api_method", "api_url", "shell_script", "script_content", "script", "working_dir")
    return any(field in data for field in payload_fields)


def _rebuild_action_payload(job: Job, data: dict) -> dict:
    action_payload = dict(job.action_payload or {})
    if job.action_type == "api_call":
        if "api_method" in data:
            action_payload["method"] = data["api_method"]
        if "api_url" in data:
            action_payload["url"] = data["api_url"]
    elif job.action_type in ("shell", "python"):
        script_val = data.get("script") or data.get("shell_script") or data.get("script_content")
        if script_val:
            action_payload["script"] = script_val
            action_payload["content"] = script_val
        if "working_dir" in data:
            action_payload["working_dir"] = data["working_dir"]
    return action_payload


def _sync_action_payload(job: Job, data: dict) -> None:
    if "action_payload" in data:
        job.action_payload = data["action_payload"]
    elif _payload_needs_rebuild(data):
        job.action_payload = _rebuild_action_payload(job, data)


def update_job(db: Session, job_id: str, payload: JobUpdate, current_user: User | None = None) -> Job:
    job = get_job_or_404(db, job_id, current_user)
    data = payload.model_dump(exclude_unset=True)

    if any(key in data for key in ("schedule_type", "cron_expression", "interval_seconds")):
        job.schedule_rule = resolve_schedule_rule(payload, job.schedule_rule)

    _apply_field_aliases(job, data)
    _apply_direct_fields(job, data)
    _sync_action_payload(job, data)

    if "depends_on" in data:
        from app.application.services.job_service import JobService
        service = JobService(db)
        service.update_dependencies(job_id, data["depends_on"])

    job.sync_domain_logic()

    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: str, current_user: User | None = None) -> dict:
    job = get_job_or_404(db, job_id, current_user)
    (
        db.query(JobDependency)
        .filter((JobDependency.job_id == job.id) | (JobDependency.depends_on_job_id == job.id))
        .delete(synchronize_session=False)
    )
    db.delete(job)
    db.commit()
    return {"message": "job deleted"}


def set_job_enabled(db: Session, job_id: str, enabled: bool, current_user: User | None = None) -> Job:
    job = get_job_or_404(db, job_id, current_user)
    job.status = "enabled" if enabled else "disabled"
    job.sync_domain_logic()
    db.commit()
    db.refresh(job)
    return job


def trigger_job(db: Session, job_id: str, current_user: User | None = None, trigger_type: str = "manual") -> JobRun:
    job = get_job_or_404(db, job_id, current_user)

    if trigger_type == "schedule" and not job.enabled:
        raise HTTPException(status_code=400, detail="無法執行已停用的任務。請先啟用該 Job。")
    
    # DDD: Respect dependencies even for manual triggers
    if not job.are_dependencies_satisfied(db):
        raise HTTPException(status_code=400, detail="無法執行任務：尚未滿足相依性任務的執行條件。")

    run = JobRun(
        job_id=job.id,
        user_id=current_user.id if current_user else job.user_id,
        status="pending",
        trigger_type=trigger_type,
        triggered_by=trigger_type,
        task_type=job.task_type or job.action_type,
        script=job.script,
        working_dir=job.working_dir,
        action_type=job.action_type,
        action_payload=job.action_payload,
        timeout_seconds=job.timeout_seconds,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
