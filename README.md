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
- `backend/database/seed.sql`

If the `postgres-data` volume already exists, apply migrations manually with
`psql` or recreate the volume for a clean demo database.

## Register a User

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123","role":"admin"}'
```

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
  "task_name": "run-cleanup-script",
  "action_type": "shell",
  "action_payload": {
    "script": "hello.sh",
    "args": []
  },
  "schedule_rule": "every:10m",
  "timeout_seconds": 120,
  "max_retry": 2
}
```

Shell actions are restricted to scripts under `backend/scripts`.

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
| GET | `/api/system/health` | Health check |
| GET | `/api/metrics` | Prometheus metrics |

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
| Jielin | PostgreSQL / log / DB controller | `backend/database/`, `backend/app/models/`, `backend/app/controllers/job_run_controller.py`, `backend/app/controllers/queue_controller.py` |
| Zhengqing | UI / integration | `frontend/` |

## Production Hardening Still Needed

- HTTPS / Ingress TLS
- Kubernetes RBAC
- Secret management
- Alembic migration workflow
- Automated integration tests
- Stricter shell sandboxing
- Centralized logs with Loki or object storage
