# PostgreSQL / Log / DB Controller

This folder owns the database contract used by the FastAPI routes, scheduler,
worker, UI log viewer, and Kubernetes/PostgreSQL deployment.

## Files

- `schema.sql`: canonical PostgreSQL schema for a fresh database.
- `seed.sql`: demo users, jobs, runs, logs, and dependency data.
- `migrations/001_init.sql`: class-demo initializer that includes `schema.sql`.
- `migrations/002_db_integration_fields.sql`: legacy API/UI alignment.
- `migrations/003_job_run_snapshots_and_indexes.sql`: job run action snapshots,
  query indexes, and DB-level `updated_at` triggers.

## Tables

- `users`: login identity used by auth and job ownership.
- `jobs`: job definition, schedule, action, retry limit, timeout, and next run.
- `job_runs`: immutable execution snapshot for every scheduled/manual/retry run.
  Each run stores `action_type`, `action_payload`, and `timeout_seconds` so a
  queued/history run does not change behavior when the source job is edited.
- `job_logs`: stdout, stderr, and system log messages for UI/API search.
- `job_dependencies`: dependency graph between jobs.

## DB Controller Contract

Python DB controller functions live in:

```text
backend/app/controllers/job_controller.py
backend/app/controllers/job_run_controller.py
backend/app/controllers/queue_controller.py
backend/app/controllers/scheduler_controller.py
```

Important functions for integration:

- `create_job`, `list_jobs`, `get_job_or_404`, `update_job`, `delete_job`
- `create_job_run`, `update_job_run_status`, `retry_job_run`, `cancel_job_run`
- `save_job_log`, `get_job_run_logs`, `search_job_logs`
- `get_pending_jobs`, `lock_pending_job`, `dequeue_next_run`, `finish_run`
- `create_dependency`, `check_dependency_finished`

## Queue Locking

`queue_controller.lock_pending_job()` uses PostgreSQL row locking through
SQLAlchemy:

```python
.with_for_update(skip_locked=True)
```

Equivalent SQL:

```sql
SELECT *
FROM job_runs
WHERE status = 'pending'
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

This lets multiple Job Controller / Worker replicas pull work concurrently
without executing the same `job_runs` row twice.

## Running SQL Manually

From the repository root:

```powershell
Get-Content -Raw backend\database\schema.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\seed.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\migrations\003_job_run_snapshots_and_indexes.sql | docker compose exec -T db psql -U postgres -d jobscheduler
```

For a fresh Docker Compose database, `schema.sql` and `seed.sql` are mounted
into `/docker-entrypoint-initdb.d` and run automatically when the Postgres data
volume is empty.
