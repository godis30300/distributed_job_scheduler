# PostgreSQL / Log / DB Controller

This directory is the database contract for the Distributed Asynchronous Job
Scheduler. It is aligned with the FastAPI routes, scheduler loop, worker loop,
UI log viewer, Docker Compose, and Kubernetes PostgreSQL deployment.

## Files

- `schema.sql`: canonical schema for a fresh PostgreSQL database.
- `seed.sql`: production seed placeholder. It intentionally creates no default
  users, passwords, jobs, job runs, logs, or dependencies.
- `migrations/001_init.sql`: initial standalone initializer.
- `migrations/002_db_integration_fields.sql`: legacy API/UI alignment.
- `migrations/003_job_run_snapshots_and_indexes.sql`: queue snapshots, indexes,
  and `updated_at` triggers.
- `migrations/004_task_fields_duration_metrics.sql`: `name`, `task_type`,
  `script`, `working_dir`, `duration_ms`, and `duration_seconds_decimal`.
- `migrations/005_db_controller_functions.sql`: PostgreSQL DB controller
  functions for create, lock, status update, logs, search, and dependencies.
- `migrations/006_remove_fixed_seed_data.sql`: removes old fixed seed accounts
  and sample jobs from existing local databases.

## Required Tables

- `users`: account data for register/login, including `password_hash`.
- `jobs`: job definitions. Required user-facing fields include `id`, `name`,
  `task_type`, `script`, `description`, and `working_dir`. Compatibility fields
  `task_name`, `action_type`, `action_payload`, and `max_retry` are retained.
- `job_runs`: one immutable execution snapshot per run. It stores copied task
  fields (`task_type`, `script`, `working_dir`), status, stdout, stderr,
  error message, locks, retry count, and duration.
- `job_logs`: stdout, stderr, and system logs for API/UI log search.
- `job_dependencies`: dependency graph between jobs.

## Duration Contract

`job_runs.duration_seconds` remains an integer for legacy API/UI users.

New code should use:

- `duration_ms`: integer milliseconds, minimum `1` for completed runs.
- `duration_seconds_decimal`: decimal seconds, for example `0.023`.

This prevents fast jobs from displaying as `0s`.

## PostgreSQL DB Functions

The schema exposes these `db_*` functions for DB-level integration tests and
for other services that need direct DB helpers:

- `db_create_job`
- `db_create_job_run`
- `db_lock_pending_job`
- `db_update_job_run_status`
- `db_save_job_log`
- `db_search_job_logs`
- `db_create_dependency`
- `db_check_dependency_finished`

`db_lock_pending_job` uses:

```sql
FOR UPDATE SKIP LOCKED
```

This prevents multiple Job Controller or Worker replicas from executing the
same pending `job_runs` row.

## Python DB Controller Functions

The API uses Python controller functions in:

```text
backend/app/controllers/job_controller.py
backend/app/controllers/job_run_controller.py
backend/app/controllers/queue_controller.py
backend/app/controllers/scheduler_controller.py
```

Important functions:

- `create_job`, `list_jobs`, `get_job_or_404`, `update_job`, `delete_job`
- `create_job_run`, `update_job_run_status`, `retry_job_run`, `cancel_job_run`
- `save_job_log`, `get_job_run_logs`, `search_job_logs`
- `get_pending_jobs`, `lock_pending_job`, `dequeue_next_run`, `finish_run`
- `create_dependency`, `check_dependency_finished`

## Manual Local Test

Start services:

```powershell
docker compose up -d --build db backend worker frontend
```

Apply migrations if the database volume already existed:

```powershell
Get-Content -Raw backend\database\migrations\004_task_fields_duration_metrics.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\migrations\005_db_controller_functions.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\migrations\006_remove_fixed_seed_data.sql | docker compose exec -T db psql -U postgres -d jobscheduler
```

Run the DB smoke test:

```powershell
docker compose exec -T backend python scripts/db_smoke_test.py
```

Successful output ends with:

```text
DB SMOKE TEST PASSED
```

## Fresh Database

For a clean local database:

```powershell
docker compose down -v
docker compose up -d --build db backend worker frontend
```

When the PostgreSQL volume is empty, Docker runs `schema.sql` and `seed.sql`
from `/docker-entrypoint-initdb.d` automatically.

`seed.sql` does not insert users. Real accounts are created through
`POST /api/auth/register`, and the backend stores bcrypt hashes in
`users.password_hash`.
