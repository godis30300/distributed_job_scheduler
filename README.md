# Distributed Asynchronous Job Scheduler

這是一個可實作課堂專題的全端骨架，符合：

- Python FastAPI 後端
- Model / Controller / Router 分層
- PostgreSQL 儲存 Job、Job Run、Log
- Scheduler 掃描到期任務
- Worker 非同步執行任務
- React 前端 UI
- Docker Compose 一鍵啟動
- Kubernetes manifests 範例
- Prometheus `/api/metrics` 指標端點

## 專案架構

```text
distributed_job_scheduler/
├── backend/
│   ├── app/
│   │   ├── core/          # config, db, security
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── controllers/   # business logic
│   │   ├── routers/       # FastAPI routers
│   │   ├── services/      # scheduler loop, worker loop, executors
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   └── App.jsx
│   ├── package.json
│   └── Dockerfile
├── deploy/k8s/
└── docker-compose.yml
```

## 快速啟動

```bash
docker compose up --build
```

啟動後：

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

## 預設帳號

第一次請先到前端 Register 建立帳號，或用 API：

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123","role":"admin"}'
```

## Job Action Payload 範例

### API Call 任務

```json
{
  "task_name": "call-health-api",
  "action_type": "api_call",
  "action_payload": {
    "method": "GET",
    "url": "https://example.com/health",
    "headers": {},
    "body": null
  },
  "schedule_rule": "every:5m",
  "timeout_seconds": 60,
  "max_retry": 3
}
```

### Shell 任務

> 為了安全，shell 只允許執行 `backend/scripts` 目錄中的白名單 script。

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

## Schedule Rule 支援

目前支援兩種格式：

```text
every:5m
every:1h
```

以及 cron 格式，例如：

```text
0 2 * * *
```

## 核心 API

| Method | Path | 說明 |
|---|---|---|
| POST | `/api/auth/register` | 註冊 |
| POST | `/api/auth/login` | 登入 |
| GET | `/api/auth/me` | 目前使用者 |
| POST | `/api/jobs` | 建立 Job |
| GET | `/api/jobs` | Job List |
| GET | `/api/jobs/{job_id}` | Job Detail |
| PUT | `/api/jobs/{job_id}` | 更新 Job |
| DELETE | `/api/jobs/{job_id}` | 刪除 Job |
| POST | `/api/jobs/{job_id}/trigger` | 手動觸發 |
| GET | `/api/job-runs` | 執行紀錄 |
| GET | `/api/job-runs/{run_id}` | 單次執行紀錄 |
| POST | `/api/job-runs/{run_id}/retry` | 重試 |
| POST | `/api/job-runs/{run_id}/cancel` | 取消 |
| GET | `/api/job-runs/{run_id}/logs` | Log |
| POST | `/api/scheduler/scan` | 手動掃描到期任務 |
| GET | `/api/dashboard/summary` | Dashboard 統計 |
| GET | `/api/system/health` | 系統健康檢查 |
| GET | `/api/metrics` | Prometheus metrics |

## 分工對應

| 成員 | 對應目錄 |
|---|---|
| 睿謙 | `deploy/`, `docker-compose.yml`, `backend/app/routers/system_router.py` |
| 其佑 | `backend/app/controllers/auth_controller.py`, `backend/app/controllers/job_controller.py`, `backend/app/routers/` |
| 振元 | `backend/app/services/worker_loop.py`, `backend/app/services/scheduler_loop.py`, `backend/Dockerfile` |
| 杰霖 | `backend/app/models/`, `backend/app/controllers/job_run_controller.py`, `backend/app/controllers/queue_controller.py` |
| 政卿 | `frontend/`, Dashboard、Job UI、API 串接 |

## 注意

這是教學 / 專題用骨架，已具備完整實作方向，但正式環境仍應補強：

- HTTPS / Ingress TLS
- Kubernetes RBAC
- Secret 管理
- DB migration，例如 Alembic
- 更完整的測試
- 更嚴格的 shell sandbox
- Log 拆到 Loki / Object Storage
