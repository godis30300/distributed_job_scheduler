from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.controllers.job_run_controller import search_job_logs
from app.controllers.queue_controller import finish_run, lock_pending_job
from app.core.database import SessionLocal, init_db
from app.models.job import Job
from app.models.job_log import JobLog
from app.models.job_run import JobRun
from app.models.user import User


SMOKE_USERNAME = "db_smoke_user"
SMOKE_EMAIL = "db-smoke@example.com"
SMOKE_JOB_NAME = "db-smoke-shell-job"
SMOKE_WORKER_ID = "db-smoke-worker"


REQUIRED_COLUMNS = {
    "users": {"id", "username", "email", "password_hash", "role", "created_at"},
    "jobs": {
        "id",
        "user_id",
        "task_name",
        "action_type",
        "action_payload",
        "schedule_rule",
        "status",
        "enabled",
        "timeout_seconds",
        "max_retry",
        "next_run_at",
        "created_at",
        "updated_at",
    },
    "job_runs": {
        "id",
        "job_id",
        "user_id",
        "status",
        "trigger_type",
        "triggered_by",
        "worker_id",
        "locked_by",
        "locked_until",
        "start_time",
        "end_time",
        "duration_seconds",
        "retry_count",
        "action_type",
        "action_payload",
        "timeout_seconds",
        "stdout",
        "stderr",
        "error_message",
        "created_at",
        "updated_at",
    },
    "job_logs": {"id", "job_run_id", "log_level", "stream", "message", "created_at"},
    "job_dependencies": {"id", "job_id", "depends_on_job_id", "required_status", "created_at"},
}


def step(message: str) -> None:
    print(f"[db-smoke] {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_schema(db) -> None:
    rows = db.execute(
        text(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN ('users', 'jobs', 'job_runs', 'job_logs', 'job_dependencies')
            """
        )
    ).all()

    actual: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        actual.setdefault(table_name, set()).add(column_name)

    missing: list[str] = []
    for table_name, columns in REQUIRED_COLUMNS.items():
        if table_name not in actual:
            missing.append(f"{table_name}: table missing")
            continue
        missing_columns = sorted(columns - actual[table_name])
        if missing_columns:
            missing.append(f"{table_name}: missing {', '.join(missing_columns)}")

    if missing:
        details = "\n  - ".join(missing)
        raise RuntimeError(
            "Database schema is not up to date.\n"
            f"  - {details}\n"
            "For a clean local test, run: docker compose down -v ; docker compose up -d db backend"
        )


def clean_previous_smoke_data(db) -> None:
    old_job = db.query(Job).filter(Job.task_name == SMOKE_JOB_NAME).first()
    if old_job:
        db.delete(old_job)
        db.commit()


def ensure_smoke_user(db) -> User:
    user = db.query(User).filter(User.username == SMOKE_USERNAME).first()
    if user:
        return user

    user = User(
        username=SMOKE_USERNAME,
        email=SMOKE_EMAIL,
        password_hash="db-smoke-not-a-real-password-hash",
        role="operator",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_smoke_job_and_run(db, user: User) -> tuple[Job, JobRun]:
    job = Job(
        user_id=user.id,
        task_name=SMOKE_JOB_NAME,
        action_type="shell",
        action_payload={"script": "hello.sh", "args": []},
        schedule_rule="manual",
        status="enabled",
        enabled=True,
        timeout_seconds=30,
        max_retry=1,
        description="DB smoke test job; safe to delete",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    run = JobRun(
        job_id=job.id,
        user_id=user.id,
        status="pending",
        trigger_type="manual",
        triggered_by="db-smoke-test",
        retry_count=0,
        action_type=job.action_type,
        action_payload=job.action_payload,
        timeout_seconds=job.timeout_seconds,
        created_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return job, run


def print_table_counts(db) -> None:
    for table_name in ("users", "jobs", "job_runs", "job_logs", "job_dependencies"):
        count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
        step(f"{table_name}: {count} rows")


def main() -> int:
    try:
        init_db()
        db = SessionLocal()
    except SQLAlchemyError as exc:
        print("[db-smoke] Cannot connect to database.")
        print(f"[db-smoke] {exc}")
        print("[db-smoke] Make sure db/backend are running: docker compose up -d db backend")
        return 1

    try:
        step("checking required tables and columns")
        check_schema(db)

        step("current table counts")
        print_table_counts(db)

        step("creating smoke user/job/job_run")
        clean_previous_smoke_data(db)
        user = ensure_smoke_user(db)
        job, run = create_smoke_job_and_run(db, user)
        step(f"created job={job.id} run={run.id}")

        step("locking one pending run with FOR UPDATE SKIP LOCKED")
        locked_run = lock_pending_job(db, SMOKE_WORKER_ID, lock_seconds=60)
        require(locked_run is not None, "expected one pending run to be locked")
        require(locked_run.id == run.id, f"locked unexpected run: {locked_run.id}")
        require(locked_run.status == "running", "locked run should be running")
        require(locked_run.locked_by == SMOKE_WORKER_ID, "locked_by was not saved")
        step(f"locked run={locked_run.id} worker={locked_run.locked_by}")

        step("finishing run and saving stdout/stderr/logs")
        finished_run = finish_run(
            db,
            locked_run.id,
            "success",
            stdout="db smoke stdout",
            stderr="",
        )
        require(finished_run is not None, "finish_run returned None")
        require(finished_run.status == "success", "finished run should be success")
        require(finished_run.stdout == "db smoke stdout", "stdout was not saved")
        require(finished_run.end_time is not None, "end_time was not saved")

        logs = db.query(JobLog).filter(JobLog.job_run_id == run.id).order_by(JobLog.created_at.asc()).all()
        require(logs, "expected job_logs rows for the smoke run")
        require(any(log.stream == "stdout" for log in logs), "stdout log was not saved")
        require(any("Run finished: success" in log.message for log in logs), "finish system log was not saved")
        step(f"saved {len(logs)} logs for run={run.id}")

        step("testing search_job_logs(task_name/status)")
        search_results = search_job_logs(db, task_name=SMOKE_JOB_NAME, status="success", limit=20)
        require(any(log.job_run_id == run.id for log in search_results), "search_job_logs did not find smoke logs")

        step("final table counts")
        print_table_counts(db)

        print("\nDB SMOKE TEST PASSED")
        print(f"Smoke job name: {SMOKE_JOB_NAME}")
        print(f"Smoke run id:   {run.id}")
        return 0
    except Exception as exc:
        db.rollback()
        print("\nDB SMOKE TEST FAILED")
        print(f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
