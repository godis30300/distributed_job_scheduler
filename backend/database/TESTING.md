# Local DB Testing SOP

Run all commands from the repository root:

```powershell
cd C:\Users\1\Downloads\distributed_job_scheduler-postgresql-db\distributed_job_scheduler-postgresql-db
```

## 1. Start from a clean local database

This deletes only the local Docker Compose Postgres volume:

```powershell
docker compose down -v
```

Start Postgres and backend:

```powershell
docker compose up -d db backend
```

Check status:

```powershell
docker compose ps
docker compose logs db
```

`db` should show `healthy`.

## 2. Verify tables exist

```powershell
docker compose exec db psql -U postgres -d jobscheduler -c "\dt"
```

Expected tables:

```text
users
jobs
job_runs
job_logs
job_dependencies
```

## 3. Verify important job_runs columns

```powershell
docker compose exec db psql -U postgres -d jobscheduler -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'job_runs' ORDER BY ordinal_position;"
```

Important columns:

```text
action_type
action_payload
timeout_seconds
stdout
stderr
error_message
locked_by
locked_until
duration_seconds
```

## 4. Verify seed data

```powershell
docker compose exec db psql -U postgres -d jobscheduler -c "SELECT id, username, role FROM users;"
docker compose exec db psql -U postgres -d jobscheduler -c "SELECT id, task_name, action_type, schedule_rule, status FROM jobs;"
docker compose exec db psql -U postgres -d jobscheduler -c "SELECT id, job_id, status, action_type, timeout_seconds FROM job_runs;"
docker compose exec db psql -U postgres -d jobscheduler -c "SELECT id, job_run_id, log_level, stream, message FROM job_logs;"
```

## 5. Run the backend DB smoke test

This test uses the backend DB controllers, not raw SQL only. It verifies:

- backend can connect to PostgreSQL
- required tables and columns exist
- test user/job/job_run can be created
- pending run can be locked with `FOR UPDATE SKIP LOCKED`
- run can be finished as `success`
- stdout and system logs are saved
- log search by task/status works

```powershell
docker compose exec backend python scripts/db_smoke_test.py
```

Expected final output:

```text
DB SMOKE TEST PASSED
```

If the script says the schema is not up to date, run:

```powershell
docker compose down -v
docker compose up -d db backend
docker compose exec backend python scripts/db_smoke_test.py
```

## 6. Optional: inspect the smoke test rows

```powershell
docker compose exec db psql -U postgres -d jobscheduler -c "SELECT id, task_name, action_type FROM jobs WHERE task_name = 'db-smoke-shell-job';"
docker compose exec db psql -U postgres -d jobscheduler -c "SELECT id, status, action_type, stdout, error_message FROM job_runs WHERE triggered_by = 'db-smoke-test';"
docker compose exec db psql -U postgres -d jobscheduler -c "SELECT log_level, stream, message FROM job_logs WHERE job_run_id IN (SELECT id FROM job_runs WHERE triggered_by = 'db-smoke-test') ORDER BY created_at;"
```

## 7. Full app test

```powershell
docker compose up -d worker frontend
docker compose ps
```

Expected services:

```text
db        Up ... healthy
backend   Up ...
worker    Up ...
frontend  Up ...
```

Check backend health:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/system/health | Select-Object -ExpandProperty Content
```

Expected response contains:

```json
{
  "status": "healthy",
  "database": "connected",
  "api": "running"
}
```

Check API docs and frontend:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/docs | Select-Object -ExpandProperty StatusCode
Invoke-WebRequest -UseBasicParsing http://localhost:5173 | Select-Object -ExpandProperty StatusCode
```

Both should return:

```text
200
```

Open in browser:

```text
Backend API: http://localhost:8000/docs
Frontend:    http://localhost:5173
```

If a manually triggered `job_run` stays `pending`, start the worker:

```powershell
docker compose up -d worker
```
