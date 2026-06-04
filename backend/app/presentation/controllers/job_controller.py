from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain.entities.job import Job
from app.domain.entities.job_run import JobRun
from app.domain.entities.user import User
from app.presentation.dtos.job_schema import JobCreate, JobUpdate
from app.services.schedule_utils import resolve_schedule_rule
from app.infrastructure.repositories.job_repository import JobRepository


ACTIVE_JOB_STATUSES = ("enabled", "active")


def create_job(db: Session, payload: JobCreate, current_user: User) -> Job:
    from app.application.services.job_service import JobService
    service = JobService(db)
    try:
        return service.create_job(payload, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


def list_jobs(db: Session, status: str | None = None, keyword: str | None = None) -> list[Job]:
    repo = JobRepository(db)
    
    # We can still use raw query for complex ilike if BaseRepository doesn't support it yet
    # but let's see if we can use repo.list
    if not status and not keyword:
        return repo.list()
        
    query = db.query(Job)
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


def get_job_or_404(db: Session, job_id: str) -> Job:
    repo = JobRepository(db)
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def update_job(db: Session, job_id: str, payload: JobUpdate) -> Job:
    job = get_job_or_404(db, job_id)
    data = payload.model_dump(exclude_unset=True)

    # 1. Handle schedule updates using domain utility
    if any(key in data for key in ("schedule_type", "cron_expression", "interval_seconds")):
        job.schedule_rule = resolve_schedule_rule(payload, job.schedule_rule)

    # 2. Handle simple field updates
    if "action" in data:
        job.action_type = data["action"]
    if "task_type" in data:
        job.task_type = data["task_type"]
    if "retry_limit" in data:
        job.max_retry = data["retry_limit"]
    
    # 3. Direct updates
    for key in ("name", "task_name", "script", "working_dir", "status", "timeout_seconds", "description"):
        if key in data:
            setattr(job, key, data[key])
    
    if "action_payload" in data:
        job.action_payload = data["action_payload"]
    else:
        # Re-build action_payload if flat fields were updated but action_payload was not provided
        if any(key in data for key in ("api_method", "api_url", "shell_script", "script_content", "script", "working_dir")):
            ap = dict(job.action_payload)
            if job.action_type == "api_call":
                if "api_method" in data: ap["method"] = data["api_method"]
                if "api_url" in data: ap["url"] = data["api_url"]
            elif job.action_type in ("shell", "python"):
                if "shell_script" in data: ap["script"] = data["shell_script"]
                if "script" in data: ap["script"] = data["script"]
                if "script_content" in data: ap["content"] = data["script_content"]
                if "working_dir" in data: ap["working_dir"] = data["working_dir"]
            job.action_payload = ap

    # 4. Handle dependencies
    if "depends_on" in data:
        from app.application.services.job_service import JobService
        service = JobService(db)
        service.update_dependencies(job_id, data["depends_on"])

    # 5. DDD: Re-sync state
    job.sync_domain_logic()

    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: str) -> dict:
    job = get_job_or_404(db, job_id)
    job.status = "deleted"
    job.sync_domain_logic()
    db.commit()
    return {"message": "job deleted"}


def set_job_enabled(db: Session, job_id: str, enabled: bool) -> Job:
    job = get_job_or_404(db, job_id)
    job.status = "enabled" if enabled else "disabled"
    job.sync_domain_logic()
    db.commit()
    db.refresh(job)
    return job


def trigger_job(db: Session, job_id: str, current_user: User | None = None, trigger_type: str = "manual") -> JobRun:
    job = get_job_or_404(db, job_id)

    if not job.enabled:
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
