from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_dependency import JobDependency
from app.models.job_run import JobRun
from app.services.schedule_utils import compute_next_run, utcnow


def dependencies_satisfied(db: Session, job_id: str) -> bool:
    deps = db.query(JobDependency).filter(JobDependency.job_id == job_id).all()
    for dep in deps:
        latest_run = (
            db.query(JobRun)
            .filter(JobRun.job_id == dep.depends_on_job_id)
            .order_by(JobRun.created_at.desc())
            .first()
        )
        if not latest_run or latest_run.status != dep.required_status:
            return False
    return True


def scan_due_jobs(db: Session) -> dict:
    now = utcnow()

    due_jobs = (
        db.query(Job)
        .filter(Job.enabled.is_(True))
        .filter(Job.status.in_(("enabled", "active")))
        .filter(Job.next_run_at.isnot(None))
        .filter(Job.next_run_at <= now)
        .with_for_update(skip_locked=True)
        .all()
    )

    created_runs = []
    for job in due_jobs:
        if not dependencies_satisfied(db, job.id):
            job.next_run_at = compute_next_run(job.schedule_rule, now)
            continue

        run = JobRun(
            job_id=job.id,
            user_id=job.user_id,
            status="pending",
            trigger_type="schedule",
            triggered_by="schedule",
            action_payload=job.action_payload,
        )
        db.add(run)
        job.last_run_at = now
        job.next_run_at = compute_next_run(job.schedule_rule, now)
        created_runs.append(run)

    db.commit()

    return {
        "scanned_at": now.isoformat(),
        "created_runs": len(created_runs),
        "run_ids": [run.id for run in created_runs],
    }


def scheduler_status() -> dict:
    return {"status": "running", "mode": "db-lock", "leader": "single-active-by-db-lock"}
