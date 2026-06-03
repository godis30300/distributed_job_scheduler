from sqlalchemy.orm import Session
from app.domain.entities.job import Job
from app.domain.entities.job_dependency import JobDependency
from app.domain.entities.job_run import JobRun
from app.infrastructure.repositories.job_repository import JobRepository
from app.presentation.dtos.job_schema import JobCreate, JobUpdate
from app.services.schedule_utils import resolve_schedule_rule, compute_next_run, utcnow
from fastapi import HTTPException

class JobService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = JobRepository(db)

    def create_job(self, payload: JobCreate, user_id: str) -> Job:
        # Check if already exists
        if self.repository.find_by_task_name(payload.task_name):
            raise ValueError(f"Job with task_name '{payload.task_name}' already exists")

        # Map schema to model
        task_name = payload.task_name
        action_type = payload.action or payload.task_type
        
        job = Job(
            name=payload.name or task_name,
            task_name=task_name,
            task_type=payload.task_type or action_type,
            script=payload.script,
            working_dir=payload.working_dir,
            action_type=action_type,
            action_payload=payload.action_payload or {},
            schedule_rule=resolve_schedule_rule(payload),
            timeout_seconds=payload.timeout_seconds,
            max_retry=payload.retry_limit,
            status=payload.status or "enabled",
            description=payload.description,
            user_id=user_id,
        )
        
        # DDD: Sync domain logic (next_run_at calculation, etc.)
        job.sync_domain_logic()
        
        self.repository.add(job)
        self.repository.flush() # Get ID without committing yet

        # Handle dependencies
        if payload.depends_on:
            for dep_name in payload.depends_on:
                dep_job = self.repository.find_by_task_name(dep_name)
                if not dep_job:
                    # Try by ID if not found by name
                    dep_job = self.repository.get(dep_name)
                
                if not dep_job:
                    raise ValueError(f"Dependency job '{dep_name}' not found")
                
                dependency = JobDependency(
                    job_id=job.id,
                    depends_on_job_id=dep_job.id,
                    required_status="success"
                )
                self.db.add(dependency)
        
        self.repository.commit()
        self.repository.refresh(job)
        return job

    def get_job(self, job_id: str) -> Job:
        job = self.repository.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    def list_jobs(self) -> list[Job]:
        return self.repository.list()

    def scan_due_jobs(self) -> list[JobRun]:
        now = utcnow()
        # Find due jobs
        due_jobs = (
            self.db.query(Job)
            .filter(Job.enabled.is_(True))
            .filter(Job.status.in_(("enabled", "active")))
            .filter(Job.next_run_at.isnot(None))
            .filter(Job.next_run_at <= now)
            .with_for_update(skip_locked=True)
            .all()
        )

        created_runs = []
        for job in due_jobs:
            if not job.are_dependencies_satisfied(self.db):
                continue

            run = JobRun(
                job_id=job.id,
                user_id=job.user_id,
                status="pending",
                trigger_type="schedule",
                triggered_by="schedule",
                task_type=job.task_type or job.action_type,
                script=job.script,
                working_dir=job.working_dir,
                action_type=job.action_type,
                action_payload=job.action_payload,
                timeout_seconds=job.timeout_seconds,
            )
            self.db.add(run)
            job.last_run_at = now
            job.next_run_at = compute_next_run(job.schedule_rule, now)
            created_runs.append(run)

        self.db.commit()
        return created_runs
