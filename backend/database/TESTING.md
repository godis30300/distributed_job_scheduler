# Local DB/API Testing SOP

Run all commands from the repository root.

## 1. Start Docker

```powershell
docker compose up -d --build db backend worker frontend
docker compose ps
```

Expected services:

```text
db        Up ... healthy
backend   Up ...
worker    Up ...
frontend  Up ...
```

## 2. Apply DB Migrations

If the Postgres volume already existed, apply the newest migrations manually:

```powershell
Get-Content -Raw backend\database\migrations\004_task_fields_duration_metrics.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\migrations\005_db_controller_functions.sql | docker compose exec -T db psql -U postgres -d jobscheduler
```

For a fully clean database:

```powershell
docker compose down -v
docker compose up -d --build db backend worker frontend
```

## 3. Verify Required DB Tables

```powershell
docker compose exec -T db psql -U postgres -d jobscheduler -c "\dt"
```

Expected tables:

```text
users
jobs
job_runs
job_logs
job_dependencies
```

## 4. Verify Required Job Columns

```powershell
docker compose exec -T db psql -U postgres -d jobscheduler -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'jobs' AND column_name IN ('id','name','task_type','script','description','working_dir') ORDER BY column_name;"
```

Expected columns:

```text
id
name
task_type
script
description
working_dir
```

## 5. Verify Required Job Run Columns

```powershell
docker compose exec -T db psql -U postgres -d jobscheduler -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'job_runs' AND column_name IN ('task_type','script','working_dir','duration_ms','duration_seconds_decimal','stdout','stderr','error_message') ORDER BY column_name;"
```

Expected important columns:

```text
task_type
script
working_dir
duration_ms
duration_seconds_decimal
stdout
stderr
error_message
```

## 6. Verify DB Functions

```powershell
docker compose exec -T db psql -U postgres -d jobscheduler -c "SELECT proname FROM pg_proc JOIN pg_namespace ON pg_namespace.oid = pg_proc.pronamespace WHERE pg_namespace.nspname = 'public' AND proname LIKE 'db_%' ORDER BY proname;"
```

Expected functions:

```text
db_check_dependency_finished
db_create_dependency
db_create_job
db_create_job_run
db_lock_pending_job
db_save_job_log
db_search_job_logs
db_update_job_run_status
```

## 7. Run DB Smoke Test

```powershell
docker compose exec -T backend python scripts/db_smoke_test.py
```

The smoke test checks:

- required tables and columns
- PostgreSQL `db_*` functions
- Python DB controller lock/update/log/search path
- `FOR UPDATE SKIP LOCKED` pending run locking
- stdout/stderr/system log persistence
- `duration_ms > 0`
- `duration_seconds_decimal > 0`
- dependency creation and dependency success check

Successful output ends with:

```text
DB SMOKE TEST PASSED
```

## 8. Run API Scenario Test

```powershell
docker compose exec -T backend python scripts/api_scenario_test.py
```

The scenario test checks:

- `GET /api/health`
- `GET /api/system/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- new-format shell job create/run/logs
- new-format python job create/run/logs
- old-format `task_name/action/action_payload/max_retry` compatibility
- failed run and retry
- `GET /api/job-runs`
- `GET /api/job-runs/logs/search`
- `GET /api/dashboard/summary`
- `GET /api/metrics`

Successful output ends with:

```text
API SCENARIO TEST PASSED
```

## 9. Health URLs

From the host machine:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/health | Select-Object -ExpandProperty Content
Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/system/health | Select-Object -ExpandProperty Content
```

Inside Docker/Kubernetes service networking, use:

```text
http://backend:8000/api/health
```
