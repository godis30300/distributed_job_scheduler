# Distributed Asynchronous Job Scheduler

DB 串接文件：`backend/database/API_DB_INTEGRATION.md`

PostgreSQL schema：`backend/database/schema.sql`

DB 已支援作業需求中的 queue lock、log、retry、dependency、failover heartbeat 與 worker 水平擴展。

這是一個可實作課堂專題的全端骨架，符合：

- Python FastAPI backend
- Model / controller / router layering
- PostgreSQL tables for users, jobs, job runs, logs, and dependencies
- Scheduler loop that creates due `job_runs`
- Worker loop that locks pending runs and executes job actions
- Django-based web UI
- Docker Compose local environment
- Kubernetes manifests and kustomize example
- Prometheus `/api/metrics` endpoint

## Project Layout

```text
distributed_job_scheduler/
|-- backend/
|   |-- app/
|   |   |-- core/
|   |   |-- models/
|   |   |-- schemas/
|   |   |-- controllers/
|   |   |-- routers/
|   |   |-- services/
|   |   `-- main.py
|   |-- database/
|   |   |-- schema.sql
|   |   |-- seed.sql
|   |   `-- migrations/
|   |-- requirements.txt
|   `-- Dockerfile
|-- frontend/
|-- deploy/k8s/
`-- docker-compose.yml
```

## Quick Start

```bash
docker compose up --build
```

Endpoints:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

For a fresh Postgres volume, Docker Compose automatically runs:

- `backend/database/schema.sql`
- `backend/database/seed.sql` (intentionally creates no default accounts)

If the `postgres-data` volume already exists, apply migrations manually with
`psql` or recreate the volume for a clean database.

## Register a User

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"operator1","email":"operator1@example.com","password":"strongpass123","role":"operator"}'
```

The database does not ship default users or passwords. Registration stores a
real bcrypt hash in `users.password_hash`; plaintext passwords are never seeded.

## Job Payload Examples

API call job:

```json
{
  "task_name": "call-health-api",
  "action_type": "api_call",
  "action_payload": {
    "method": "GET",
    "url": "http://backend:8000/api/system/health",
    "headers": {},
    "body": null
  },
  "schedule_rule": "every:5m",
  "timeout_seconds": 60,
  "max_retry": 3
}
```

Shell job:

```json
{
  "name": "free-shell-job",
  "task_type": "shell",
  "script": "echo hello from user input",
  "description": "Run a Linux shell script entered by the user",
  "working_dir": "free-shell-job",
  "schedule_type": "manual",
  "timeout_seconds": 30,
  "retry_limit": 1,
  "status": "enabled"
}
```

Python job:

```json
{
  "name": "free-python-job",
  "task_type": "python",
  "script": "print('hello from python')",
  "description": "Run a Python script entered by the user",
  "working_dir": "free-python-job",
  "schedule_type": "manual",
  "timeout_seconds": 30,
  "retry_limit": 1,
  "status": "enabled"
}
```

The newer job API accepts `id`, `name`, `task_type`, `script`, `description`,
`working_dir`, and log output through `job_runs` / `job_logs`. Older fields
such as `task_name`, `action`, `action_type`, `action_payload`, `retry_limit`,
and `max_retry` remain supported for team integration.

## Schedule Rules

Supported interval formats:

```text
every:5m
every:1h
```

Cron expressions are also supported, for example:

```text
0 2 * * *
```

## Core API

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Register |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Current user |
| POST | `/api/jobs` | Create job |
| GET | `/api/jobs` | List jobs |
| GET | `/api/jobs/{job_id}` | Job detail |
| PUT | `/api/jobs/{job_id}` | Update job |
| DELETE | `/api/jobs/{job_id}` | Delete job |
| POST | `/api/jobs/{job_id}/run` | Manual run |
| POST | `/api/jobs/{job_id}/trigger` | Manual run alias |
| GET | `/api/job-runs` | Run history |
| GET | `/api/job-runs/{run_id}` | Run detail |
| GET | `/api/job-runs/{run_id}/logs` | Run logs |
| GET | `/api/job-runs/logs/search` | Search logs |
| POST | `/api/job-runs/{run_id}/retry` | Retry failed run |
| POST | `/api/job-runs/{run_id}/cancel` | Cancel pending/running run |
| POST | `/api/scheduler/scan` | Manually scan due jobs |
| POST | `/api/workers/pull` | Pull and lock one pending run |
| POST | `/api/workers/{run_id}/finish` | Finish run and save output |
| GET | `/api/dashboard/summary` | Dashboard summary |
| GET | `/api/health` | Health check alias |
| GET | `/api/system/health` | Health check |
| GET | `/api/metrics` | Prometheus metrics |

## Duration

`job_runs` stores both:

- `duration_seconds_decimal`: precise seconds with milliseconds, for example `0.023`.
- `duration_ms`: precise millisecond duration for fast container jobs.
- `duration_seconds`: rounded up to at least `1` second for old clients.

The frontend displays `run.duration`, which uses `duration_seconds_decimal`, so
fast shell/python tasks show values such as `0.023s` instead of `0s`.

## Monitoring

Prometheus scrapes `/api/metrics` for application metrics, including job run
counts by status. Kubernetes/cAdvisor and kube-state-metrics are configured in
`deploy/k8s/07-monitoring.yaml` for:

- container CPU: `container_cpu_usage_seconds_total`
- container memory: `container_memory_working_set_bytes`
- pod restarts: `kube_pod_container_status_restarts_total`

The same file also includes a Grafana dashboard ConfigMap for pending/running
jobs, CPU, memory, and pod restart panels.

## Test Commands

Run from the repository root after starting Docker Compose:

```powershell
docker compose up -d --build db backend worker frontend
Get-Content -Raw backend\database\migrations\004_task_fields_duration_metrics.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\migrations\005_db_controller_functions.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\migrations\006_remove_fixed_seed_data.sql | docker compose exec -T db psql -U postgres -d jobscheduler
docker compose exec -T backend python scripts/db_smoke_test.py
docker compose exec -T backend python scripts/api_scenario_test.py
docker compose exec -T backend python scripts/strict_full_system_test.py
docker compose config
kubectl kustomize .
```

Expected successful outputs:

```text
DB SMOKE TEST PASSED
API SCENARIO TEST PASSED
STRICT FULL SYSTEM TEST PASSED
```

The DB smoke test validates schema columns, PostgreSQL `db_*` functions, queue
locking, logs, decimal duration, and dependencies. The API scenario test covers
register/login/me, health aliases, new shell/python jobs, old payload
compatibility, retry, log search, dashboard summary, and metrics.

The strict full system test is the project-level check. It uses no seeded
account: it registers a real user, verifies the bcrypt password hash in the DB,
logs in with JWT, changes the password, and exercises job CRUD, shell/python
execution, retry, cancel, worker finish, scheduler, logs, dashboard, and
metrics.

## GitLab CI

This repository includes a minimal GitLab pipeline in `.gitlab-ci.yml`.

Pipeline jobs:

- `backend_pytest`: runs the fast pytest slice for backend scheduling and worker behavior.
- `backend_db_smoke`: starts PostgreSQL, applies schema plus migrations, and runs `python scripts/db_smoke_test.py`.
- `docker_build_backend`: builds the backend Docker image on the default branch and tags.
- `docker_build_frontend`: builds the frontend Docker image on the default branch and tags.

The test jobs use a GitLab PostgreSQL service with:

- `DATABASE_URL=postgresql+psycopg2://postgres:postgres@postgres:5432/jobscheduler`
- `JWT_SECRET_KEY=gitlab-ci-secret`

This version does not push images or deploy them. If your GitLab runner does
not allow Docker-in-Docker, keep the test jobs and replace the two image build
jobs with the image builder supported by your runner.

## Static Code Analysis (SonarQube)

The project includes a SonarQube instance for static code analysis.

### Setup & Scan

1. **Start SonarQube Server**:
   ```bash
   docker compose up -d sonarqube
   ```
2. **Run Scanner**:
   ```bash
   ./run-sonar.sh
   ```

### Access Results

- **URL**: [http://localhost:9000](http://localhost:9000)
- **Project**: `distributed-job-scheduler`
- **Credentials**:
  - **Username**: `admin`
  - **Password**: `AdminPassword123!`

## Kubernetes

Use kustomize from the repository root so PostgreSQL receives the schema and
seed SQL as a ConfigMap:

```bash
kubectl apply -k .
```

`deploy/k8s/02-postgres.yaml` mounts the generated `postgres-init-sql`
ConfigMap to `/docker-entrypoint-initdb.d` and stores data in a PVC.

## Team Ownership

| Member | Area | Main paths |
|---|---|---|
| Ruiqian | Environment / Kubernetes / monitoring | `deploy/`, `docker-compose.yml`, system router |
| Qiyou | Python API / auth / routes | `backend/app/controllers/auth_controller.py`, `backend/app/controllers/job_controller.py`, `backend/app/routers/` |
| Zhenyuan | Job Controller / worker / task execution | `backend/app/services/worker_loop.py`, `backend/app/services/scheduler_loop.py`, `backend/Dockerfile` |
| DB owner | PostgreSQL / log / DB controller | `backend/database/`, `backend/app/models/`, `backend/app/controllers/job_run_controller.py`, `backend/app/controllers/queue_controller.py` |
| Zhengqing | UI / integration | `frontend/` |

## Production Hardening Still Needed

- HTTPS / Ingress TLS
- Kubernetes RBAC
- Secret management
- Alembic migration workflow
- Automated integration tests
- Stricter shell sandboxing
- Centralized logs with Loki or object storage
