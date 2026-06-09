# Distributed Job Scheduler

Distributed Job Scheduler is a containerized job scheduling platform with a
FastAPI backend, PostgreSQL queue storage, worker and scheduler loops, and a
Django frontend. It supports manual and scheduled jobs, shell and Python task
execution, API-call tasks, retries, cancelation, execution logs, dashboard
metrics, and Kubernetes deployment manifests.

## What This Project Shows

- User registration, login, JWT authentication, and bcrypt password storage.
- Job CRUD for both new payloads (`name`, `task_type`, `script`) and legacy
  payloads (`task_name`, `action`, `action_payload`).
- PostgreSQL-backed queue locking with `SKIP LOCKED` behavior.
- Worker execution for shell, Python, API-call, retry, long-task, and failure
  test actions.
- Scheduler scanning for due jobs.
- Job run history, log search, retry, cancel, heartbeat, and manual worker
  finish endpoints.
- Prometheus metrics at `/api/metrics`.
- Docker Compose for local development.
- Kubernetes and kustomize manifests for deployment review.

## Architecture

```text
frontend (Django UI)
        |
        v
backend (FastAPI REST API)
        |
        v
PostgreSQL (users, jobs, job_runs, job_logs, dependencies)
        ^
        |
worker loop      scheduler loop
locks runs       creates due runs
executes tasks   from enabled schedules
```

Core services:

- `db`: PostgreSQL 16 initialized from `backend/database/schema.sql`.
- `backend`: FastAPI app served by Uvicorn on port `8000`.
- `worker`: locks pending runs and executes job actions.
- `scheduler`: scans enabled schedules and creates due runs.
- `frontend`: Django UI served on port `5173`.

## Repository Layout

```text
distributed_job_scheduler/
|-- backend/
|   |-- app/
|   |   |-- application/services/
|   |   |-- core/
|   |   |-- domain/entities/
|   |   |-- infrastructure/
|   |   |-- presentation/api/
|   |   |-- presentation/controllers/
|   |   `-- main.py
|   |-- database/
|   |   |-- schema.sql
|   |   |-- seed.sql
|   |   `-- migrations/
|   |-- scripts/
|   |   |-- db_smoke_test.py
|   |   |-- api_scenario_test.py
|   |   `-- strict_full_system_test.py
|   |-- tests/
|   |-- requirements.txt
|   `-- Dockerfile
|-- frontend/
|   |-- scheduler_frontend/
|   |-- ui/
|   |-- requirements.txt
|   `-- Dockerfile
|-- deploy/k8s/
|-- k3s/
|-- docker-compose.yml
|-- kustomization.yaml
`-- Makefile
```

## Docker Images And Ports

Local Docker Compose builds these project images:

| Service | Image source | Port |
|---|---|---|
| `db` | `postgres:16` | `5432` |
| `backend` | `backend/Dockerfile` | `8000` |
| `scheduler` | `backend/Dockerfile` | internal |
| `worker` | `backend/Dockerfile` | internal |
| `frontend` | `frontend/Dockerfile` | `5173` |

Kubernetes manifests under `deploy/k8s/` and `k3s/` contain registry image
names for deployment. Update those image names to match the registry required
by your course, report, or cluster before applying them.

## Quick Start

Create `.env` from the template:

```bash
cp .env.example .env
```

Required values:

```text
POSTGRES_DB=jobscheduler
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me-postgres-password
JWT_SECRET_KEY=change-me-jwt-secret
SECRET_KEY=change-me-django-secret
ALLOWED_HOSTS=localhost,127.0.0.1
BACKEND_API_URL=http://backend:8000
CORS_ORIGINS=http://localhost:5173
```

Start the local stack:

```bash
docker compose up -d --build db backend scheduler worker frontend
```

Open:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000/api`
- API docs: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/api/metrics`

Stop the stack:

```bash
docker compose down
```

Reset the database volume:

```bash
docker compose down -v
```

## Main API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/auth/register` | Register a real user |
| `POST` | `/api/auth/login` | Login and receive JWT |
| `GET` | `/api/auth/me` | Read current user |
| `POST` | `/api/jobs` | Create a job |
| `GET` | `/api/jobs` | List/search jobs |
| `GET` | `/api/jobs/{job_id}` | Read job detail |
| `PUT` | `/api/jobs/{job_id}` | Update job fields or script |
| `PATCH` | `/api/jobs/{job_id}/enable` | Enable a job |
| `PATCH` | `/api/jobs/{job_id}/disable` | Disable a job |
| `POST` | `/api/jobs/{job_id}/run` | Trigger a manual run |
| `POST` | `/api/jobs/{job_id}/trigger` | Trigger alias |
| `GET` | `/api/job-runs` | List run history |
| `GET` | `/api/job-runs/{run_id}` | Read run detail |
| `GET` | `/api/job-runs/{run_id}/logs` | Read run logs |
| `GET` | `/api/job-runs/logs/search` | Search logs by task/status/level |
| `POST` | `/api/job-runs/{run_id}/retry` | Retry failed or timed-out run |
| `POST` | `/api/job-runs/{run_id}/cancel` | Cancel pending/running run |
| `POST` | `/api/scheduler/scan` | Manually scan due schedules |
| `GET` | `/api/scheduler/status` | Scheduler health/status |
| `POST` | `/api/workers/pull` | Pull and lock a pending run |
| `POST` | `/api/workers/{run_id}/heartbeat` | Update run heartbeat |
| `POST` | `/api/workers/{run_id}/finish` | Finish a run and save output |
| `GET` | `/api/dashboard/summary` | Dashboard totals |
| `GET` | `/api/health` | Health alias |
| `GET` | `/api/system/health` | System health |
| `GET` | `/api/metrics` | Prometheus metrics |

## Job Payload Examples

Shell job:

```json
{
  "name": "hello-shell",
  "task_type": "shell",
  "script": "echo hello from shell",
  "working_dir": "hello-shell",
  "schedule_type": "manual",
  "timeout_seconds": 30,
  "retry_limit": 1,
  "status": "enabled"
}
```

Python job:

```json
{
  "name": "hello-python",
  "task_type": "python",
  "script": "print('hello from python')",
  "working_dir": "hello-python",
  "schedule_type": "manual",
  "timeout_seconds": 30,
  "retry_limit": 1,
  "status": "enabled"
}
```

Legacy API-call job:

```json
{
  "task_name": "call-health-api",
  "action": "api_call",
  "action_payload": {
    "method": "GET",
    "url": "http://backend:8000/api/system/health",
    "headers": {},
    "body": null
  },
  "schedule_rule": "every:5m",
  "timeout_seconds": 60,
  "max_retry": 3,
  "status": "enabled"
}
```

## Testing

Run unit tests without PostgreSQL:

```powershell
$env:DATABASE_URL='sqlite:///./test.db'
$env:JWT_SECRET_KEY='unit-test-secret'
$env:PYTHONPATH='.'
cd backend
python -m pytest tests/unit/
```

Run project-level checks after Docker Compose is up:

```powershell
docker compose exec -T backend python scripts/db_smoke_test.py
docker compose exec -T backend python scripts/api_scenario_test.py
docker compose exec -T backend python scripts/strict_full_system_test.py
docker compose config
kubectl kustomize .
python -m compileall backend frontend
```

Expected successful outputs:

```text
DB SMOKE TEST PASSED
API SCENARIO TEST PASSED
STRICT FULL SYSTEM TEST PASSED
```

What the checks cover:

- `db_smoke_test.py`: schema, required columns, PostgreSQL `db_*` functions,
  queue locking, logs, duration fields, dependencies, and final row counts.
- `api_scenario_test.py`: auth, health, shell/python jobs, legacy payloads,
  retry, run history, log search, dashboard, and metrics.
- `strict_full_system_test.py`: seeded admin login, bcrypt password hash,
  password change, job CRUD/update, execution output, retry, cancel, heartbeat,
  worker finish, scheduler, system endpoints, metrics, and soft delete.


## Kubernetes

Render manifests:

```bash
kubectl kustomize .
```

Apply manifests:

```bash
kubectl apply -k .
```

Before deploying, update image names and secrets for your registry and cluster.
The generated resources include namespace, config maps, secrets, PostgreSQL,
backend, frontend, scheduler, worker, services, ingress, and monitoring config.

## CI

GitHub Actions is defined in `.github/workflows/ci.yml`.

The workflow:

- Starts PostgreSQL 16.
- Applies `backend/database/schema.sql` and migrations.
- Runs backend unit tests with SQLite.
- Runs backend integration tests with PostgreSQL.
- Uploads JUnit and coverage artifacts.

## Notes

- `backend/database/seed.sql` creates a default admin user for first-time
  login: `admin / admin123` with email `admin@gmail.com`. The password is
  stored as a bcrypt hash. Users can still register through
  `/api/auth/register`.
- Disabled jobs cannot be manually triggered until they are enabled.
- Fast job durations are stored in both milliseconds and decimal seconds.
- Shell and Python jobs run inside the worker container, not on the host.
- Use `docker compose down -v` when you need a clean PostgreSQL initialization.
