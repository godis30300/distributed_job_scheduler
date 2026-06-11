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

Two deployment paths are provided:

- `deploy/k8s/` + root `kustomization.yaml` — kustomize review/render.
- `k3s/` + `k3s/deploy.sh` — opinionated, ordered deploy script for a live
  k3s/k8s cluster. This is the recommended path and is documented below.

### k3s manifests overview

| File | Resources | Purpose |
|---|---|---|
| `db.yaml` | ConfigMap, PVC, **Secret**, Deployment, Service | PostgreSQL 16 + schema init SQL + `job-scheduler-secret` |
| `backend.yaml` | Deployment, Service (NodePort `30080`) | FastAPI REST API on `:8000` |
| `scheduler.yaml` | Deployment ×2 | `scheduler` (scheduler_loop) + `worker` (worker_loop) |
| `frontend.yaml` | Deployment, Service (NodePort `30081`) | Django UI, runs `migrate` on boot, calls `http://backend:8000/api` |
| `ingress.yaml` | Ingress (`default` ns) | `/api` → backend, everything else → frontend |
| `grafana-ingress.yaml` | Ingress (`monitoring` ns) | `/grafana` → `prometheus-grafana:80` |
| `hpa-backend.yaml` | HPA | backend CPU 70%, 1–5 replicas |
| `hpa-scheduler.yaml` | HPA | scheduler CPU 70%, 1–3 replicas |
| `hpa-worker.yaml` | HPA | worker CPU 70% + custom `scheduler_queue_length`, 1–10 replicas |

### Required parameters / keys

`deploy.sh` injects all secret values from environment variables — nothing
secret is committed in the manifests. The `${...}` placeholders inside
`db.yaml` are expanded at apply time with `envsubst`.

| Env var | Required | Used by | Maps to |
|---|---|---|---|
| `POSTGRES_PASSWORD` | **yes** | `db`, `backend`, `scheduler`, `worker` | Postgres password + `DATABASE_URL` + `POSTGRES_PASSWORD` in `job-scheduler-secret` |
| `JWT_SECRET_KEY` | **yes** | `backend`, `scheduler`, `worker` | `JWT_SECRET_KEY` in `job-scheduler-secret` |
| `DJANGO_SECRET_KEY` | **yes** | `frontend` | `SECRET_KEY` in `frontend-secret` |
| `DOCKERHUB_USER` | no | `scheduler`, `worker` | Creates `registry-secret` (only needed for private images) |
| `DOCKERHUB_TOKEN` | no | `scheduler`, `worker` | Docker registry password/token |
| `INGRESS_CLASS` | no | both Ingresses | Override `ingressClassName` (e.g. `traefik`) |

Secrets the script creates for you:

- **`job-scheduler-secret`** — from `db.yaml` after `envsubst`
  (`DATABASE_URL`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `PYTHONUNBUFFERED`).
- **`frontend-secret`** — created imperatively from `DJANGO_SECRET_KEY`.
  This secret is **not** in any manifest; without it the frontend pod fails.
- **`registry-secret`** — optional, only created when `DOCKERHUB_*` are set.
  The default images are public on Docker Hub, so a missing `registry-secret`
  yields only a warning event, not a failure.

### Cluster prerequisites

| Capability | Needed for | Install |
|---|---|---|
| `kubectl` reachable cluster | everything | — |
| `envsubst` (gettext) | secret expansion | `apt install gettext-base` |
| ingress-nginx controller | `ingress.yaml`, `grafana-ingress.yaml` | k3s ships **Traefik**; install ingress-nginx or pass `INGRESS_CLASS=traefik` |
| metrics-server | all HPAs (CPU) | `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml` |
| Prometheus Adapter | worker custom metric `scheduler_queue_length` | optional — without it, worker scales on CPU only |
| kube-prometheus-stack | `grafana-ingress.yaml` target service | optional — provides `prometheus-grafana` in `monitoring` ns |

`deploy.sh` warns (does not abort) when metrics-server or the `nginx`
ingressClass is missing.

### Deploy

```bash
cd k3s

export POSTGRES_PASSWORD='change-me-postgres-password'
export JWT_SECRET_KEY='change-me-jwt-secret'
export DJANGO_SECRET_KEY='change-me-django-secret'

# Optional:
# export DOCKERHUB_USER='...'      # only for private registry
# export DOCKERHUB_TOKEN='...'
# export INGRESS_CLASS='traefik'   # default k3s ingress controller

./deploy.sh
```

The script applies resources in dependency order, waiting for each rollout:

1. `monitoring` namespace (created if absent).
2. Secrets: `registry-secret` (optional), `frontend-secret`.
3. `db` — applied via `envsubst`, then waits for `pg_isready`.
4. `backend` — waits for rollout.
5. `scheduler` + `worker`.
6. `frontend`.
7. `ingress.yaml` + `grafana-ingress.yaml`.
8. HPAs.

### Access

NodePort (always available):

- Backend API docs: `http://<node-ip>:30080/api/docs`
- Frontend: `http://<node-ip>:30081`

Through ingress (when a controller is installed):

- `http://<ingress-host>/api` → backend
- `http://<ingress-host>/` → frontend
- `http://<ingress-host>/grafana` → Grafana (requires kube-prometheus-stack)

The script prints the node IP and these URLs on completion.

### Teardown

```bash
kubectl delete -f k3s/frontend.yaml -f k3s/scheduler.yaml -f k3s/backend.yaml
kubectl delete -f k3s/ingress.yaml
kubectl delete -f k3s/hpa-backend.yaml -f k3s/hpa-scheduler.yaml -f k3s/hpa-worker.yaml
kubectl delete -f k3s/grafana-ingress.yaml
kubectl delete secret frontend-secret registry-secret --ignore-not-found
# db.yaml carries the Secret + PVC; delete the PVC too for a clean reset:
kubectl delete -f k3s/db.yaml
kubectl delete pvc db-pvc --ignore-not-found
```

### kustomize path (review only)

```bash
kubectl kustomize .     # render deploy/k8s manifests
kubectl apply -k .      # apply the kustomize set
```

Before using the kustomize path, update image names and secret values for your
registry and cluster.

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
