from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.controllers.job_run_controller import search_job_logs
from app.controllers.queue_controller import finish_run, lock_pending_job
from app.core.database import SessionLocal, init_db
from app.core.security import hash_password
from app.models.job import Job
from app.models.job_log import JobLog
from app.models.job_run import JobRun
from app.models.user import User


SMOKE_USERNAME = "db_smoke_user"
SMOKE_EMAIL = "db-smoke@example.com"
SMOKE_JOB_NAME = "db-smoke-shell-job"
SMOKE_DB_FUNCTION_JOB_NAME = "db-function-shell-job"
SMOKE_WORKER_ID = "db-smoke-worker"

REQUIRED_COLUMNS = {
    "users": {
        "id",
        "username",
        "email",
        "password_hash",
        "role",
        "created_at",
    },
    "jobs": {
        "id",
        "user_id",
        "name",
        "task_name",
        "task_type",
        "script",
        "description",
        "working_dir",
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
        "heartbeat_at",
        "duration_seconds",
        "duration_seconds_decimal",
        "duration_ms",
        "retry_count",
        "task_type",
        "script",
        "working_dir",
        "action_type",
        "action_payload",
        "timeout_seconds",
        "stdout",
        "stderr",
        "error_message",
        "created_at",
        "updated_at",
    },
    "job_logs": {
        "id",
        "job_run_id",
        "log_level",
        "stream",
        "message",
        "created_at",
    },
    "job_dependencies": {
        "id",
        "job_id",
        "depends_on_job_id",
        "required_status",
        "created_at",
    },
}

REQUIRED_FUNCTIONS = {
    "db_create_job",
    "db_create_job_run",
    "db_lock_pending_job",
    "db_update_job_run_status",
    "db_save_job_log",
    "db_search_job_logs",
    "db_create_dependency",
    "db_check_dependency_finished",
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


def check_db_functions(db) -> None:
    rows = db.execute(
        text(
            """
            SELECT proname
            FROM pg_proc
            JOIN pg_namespace ON pg_namespace.oid = pg_proc.pronamespace
            WHERE pg_namespace.nspname = 'public'
              AND proname LIKE 'db_%'
            """
        )
    ).scalars().all()
    missing = REQUIRED_FUNCTIONS - set(rows)
    require(not missing, f"missing DB functions: {', '.join(sorted(missing))}")


def clean_previous_smoke_data(db) -> None:
    old_jobs = (
        db.query(Job)
        .filter(
            (Job.task_name == SMOKE_JOB_NAME)
            | (Job.task_name == SMOKE_DB_FUNCTION_JOB_NAME)
            | (Job.task_name.like(f"{SMOKE_DB_FUNCTION_JOB_NAME}-%"))
        )
        .all()
    )
    for old_job in old_jobs:
        db.delete(old_job)
    db.commit()


def ensure_smoke_user(db) -> User:
    user = db.query(User).filter(User.username == SMOKE_USERNAME).first()
    if user:
        return user

    user = User(
        username=SMOKE_USERNAME,
        email=SMOKE_EMAIL,
        password_hash=hash_password("db-smoke-password"),
        role="operator",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_smoke_job_and_run(db, user: User) -> tuple[Job, JobRun]:
    job = Job(
        user_id=user.id,
        name=SMOKE_JOB_NAME,
        task_name=SMOKE_JOB_NAME,
        task_type="shell",
        script="echo db-smoke-controller",
        working_dir="db-smoke-controller",
        action_type="shell",
        action_payload={"script": "echo db-smoke-controller", "working_dir": "db-smoke-controller"},
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
        task_type=job.task_type,
        script=job.script,
        working_dir=job.working_dir,
        action_type=job.action_type,
        action_payload=job.action_payload,
        timeout_seconds=job.timeout_seconds,
        created_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return job, run


def exercise_python_controllers(db, user: User) -> None:
    step("testing Python DB controller queue lock and log writes")
    job, run = create_smoke_job_and_run(db, user)
    require(job.name == SMOKE_JOB_NAME, "jobs.name was not saved")
    require(job.task_type == "shell", "jobs.task_type was not saved")
    require(job.script == "echo db-smoke-controller", "jobs.script was not saved")
    require(job.working_dir == "db-smoke-controller", "jobs.working_dir was not saved")

    locked_run = lock_pending_job(db, SMOKE_WORKER_ID, lock_seconds=60)
    require(locked_run is not None, "expected one pending run to be locked")
    require(locked_run.id == run.id, f"locked unexpected run: {locked_run.id}")
    require(locked_run.status == "running", "locked run should be running")
    require(locked_run.locked_by == SMOKE_WORKER_ID, "locked_by was not saved")

    finished_run = finish_run(db, locked_run.id, "success", stdout="db smoke stdout", stderr="")
    require(finished_run is not None, "finish_run returned None")
    require(finished_run.status == "success", "finished run should be success")
    require(finished_run.duration_ms and finished_run.duration_ms > 0, "duration_ms should be > 0")
    require(
        finished_run.duration_seconds_decimal and finished_run.duration_seconds_decimal > 0,
        "duration_seconds_decimal should be > 0",
    )
    require(finished_run.stdout == "db smoke stdout", "stdout was not saved")

    logs = db.query(JobLog).filter(JobLog.job_run_id == run.id).order_by(JobLog.created_at.asc()).all()
    require(any(log.stream == "stdout" for log in logs), "stdout log was not saved")
    require(any("Run finished: success" in log.message for log in logs), "finish system log was not saved")

    search_results = search_job_logs(db, task_name=SMOKE_JOB_NAME, status="success", limit=20)
    require(any(log.job_run_id == run.id for log in search_results), "search_job_logs did not find smoke logs")


def exercise_postgres_functions(db, user: User) -> None:
    step("testing PostgreSQL db_* functions")
    job_row = db.execute(
        text(
            """
            SELECT *
            FROM db_create_job(
                :user_id,
                :name,
                'shell',
                'echo db-function-smoke',
                'DB function smoke job',
                'db-function-workdir',
                'manual',
                30,
                1,
                'enabled'
            )
            """
        ),
        {"user_id": user.id, "name": SMOKE_DB_FUNCTION_JOB_NAME},
    ).mappings().first()
    require(job_row is not None, "db_create_job returned no row")
    require(job_row["name"] == SMOKE_DB_FUNCTION_JOB_NAME, "db_create_job did not save name")
    require(job_row["task_type"] == "shell", "db_create_job did not save task_type")
    require(job_row["script"] == "echo db-function-smoke", "db_create_job did not save script")
    require(job_row["working_dir"] == "db-function-workdir", "db_create_job did not save working_dir")

    run_row = db.execute(
        text("SELECT * FROM db_create_job_run(:job_id, :user_id, 'manual', 'db-smoke-function', 0)"),
        {"job_id": job_row["id"], "user_id": user.id},
    ).mappings().first()
    require(run_row is not None, "db_create_job_run returned no row")
    require(run_row["status"] == "pending", "db_create_job_run should create pending run")
    require(run_row["task_type"] == "shell", "db_create_job_run did not snapshot task_type")
    require(run_row["script"] == "echo db-function-smoke", "db_create_job_run did not snapshot script")
    db.execute(
        text("UPDATE job_runs SET created_at = '1999-01-01T00:00:00Z' WHERE id = :run_id"),
        {"run_id": run_row["id"]},
    )
    db.commit()

    locked_row = db.execute(
        text("SELECT * FROM db_lock_pending_job('db-function-worker', 60)")
    ).mappings().first()
    require(locked_row is not None, "db_lock_pending_job returned no row")
    require(locked_row["id"] == run_row["id"], "db_lock_pending_job locked the wrong run")
    require(locked_row["status"] == "running", "db_lock_pending_job should set running")

    updated_row = db.execute(
        text("SELECT * FROM db_update_job_run_status(:run_id, 'success', 'function stdout', '', NULL)"),
        {"run_id": run_row["id"]},
    ).mappings().first()
    require(updated_row is not None, "db_update_job_run_status returned no row")
    require(updated_row["status"] == "success", "db_update_job_run_status should set success")
    require(updated_row["duration_ms"] and updated_row["duration_ms"] > 0, "DB trigger should set duration_ms")
    require(
        updated_row["duration_seconds_decimal"] and updated_row["duration_seconds_decimal"] > 0,
        "DB trigger should set decimal duration",
    )

    logs = db.execute(
        text("SELECT * FROM db_search_job_logs(:task_name, 'success', NULL, NULL, 20, 0)"),
        {"task_name": SMOKE_DB_FUNCTION_JOB_NAME},
    ).mappings().all()
    require(logs, "db_search_job_logs should find function smoke logs")
    require(any(row["stream"] == "stdout" for row in logs), "db_search_job_logs should include stdout log")

    dependency = db.execute(
        text("SELECT * FROM db_create_dependency(:job_id, :depends_on_job_id, 'success')"),
        {"job_id": job_row["id"], "depends_on_job_id": job_row["id"]},
    )
    # The self-dependency call should raise before this point.
    require(dependency is None, "self dependency should not be allowed")


def exercise_dependency_success(db, user: User) -> None:
    step("testing PostgreSQL dependency success check")
    clean_previous_smoke_data(db)
    parent_job = db.execute(
        text("SELECT * FROM db_create_job(:user_id, :name, 'shell', 'echo parent', NULL, NULL)"),
        {"user_id": user.id, "name": f"{SMOKE_DB_FUNCTION_JOB_NAME}-parent"},
    ).mappings().first()
    child_job = db.execute(
        text("SELECT * FROM db_create_job(:user_id, :name, 'shell', 'echo child', NULL, NULL)"),
        {"user_id": user.id, "name": f"{SMOKE_DB_FUNCTION_JOB_NAME}-child"},
    ).mappings().first()
    parent_run = db.execute(
        text("SELECT * FROM db_create_job_run(:job_id, :user_id, 'manual', 'db-smoke-dependency', 0)"),
        {"job_id": parent_job["id"], "user_id": user.id},
    ).mappings().first()
    db.execute(
        text("SELECT * FROM db_update_job_run_status(:run_id, 'running')"),
        {"run_id": parent_run["id"]},
    )
    db.execute(
        text("SELECT * FROM db_update_job_run_status(:run_id, 'success')"),
        {"run_id": parent_run["id"]},
    )
    db.execute(
        text("SELECT * FROM db_create_dependency(:job_id, :depends_on_job_id, 'success')"),
        {"job_id": child_job["id"], "depends_on_job_id": parent_job["id"]},
    )
    is_ready = db.execute(
        text("SELECT db_check_dependency_finished(:job_id)"),
        {"job_id": child_job["id"]},
    ).scalar_one()
    require(is_ready is True, "db_check_dependency_finished should be true after parent success")


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
        print("[db-smoke] Make sure services are running: docker compose up -d db backend")
        return 1

    try:
        step("checking required tables, columns, and DB functions")
        check_schema(db)
        check_db_functions(db)
        clean_previous_smoke_data(db)
        user = ensure_smoke_user(db)
        exercise_python_controllers(db, user)
        clean_previous_smoke_data(db)
        exercise_postgres_functions(db, user)
    except SQLAlchemyError as exc:
        db.rollback()
        if "job cannot depend on itself" in str(exc):
            step("self-dependency rejection passed")
            try:
                exercise_dependency_success(db, ensure_smoke_user(db))
                step("final table counts")
                print_table_counts(db)
                print("\nDB SMOKE TEST PASSED")
                return 0
            except Exception as nested_exc:
                db.rollback()
                print("\nDB SMOKE TEST FAILED")
                print(f"{type(nested_exc).__name__}: {nested_exc}")
                return 1
        print("\nDB SMOKE TEST FAILED")
        print(f"{type(exc).__name__}: {exc}")
        return 1
    except Exception as exc:
        db.rollback()
        print("\nDB SMOKE TEST FAILED")
        print(f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()

    print("\nDB SMOKE TEST FAILED")
    print("expected self-dependency rejection was not triggered")
    return 1


if __name__ == "__main__":
    sys.exit(main())
