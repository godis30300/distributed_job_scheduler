# Django Frontend - Distributed Asynchronous Job Scheduler

這是一個給 Distributed Asynchronous Job Scheduler 使用的 Django 前端專案。

## 功能

- 使用者登入 / 註冊
- Dashboard 任務統計
- Job List
- Create Job
- Edit Job
- Job Detail
- Manual Run
- Job Runs
- Log Viewer
- Retry Failed Job
- System Health
- RWD 響應式版面
- Demo Mode：後端 FastAPI 尚未完成時，可用 session mock data 示範 UI 流程

## 專案結構

```text
scheduler_frontend/
├── scheduler_frontend/      # Django project settings
├── ui/                      # Django app
│   ├── api_client.py         # 串接 FastAPI 的 client
│   ├── demo_store.py         # Demo Mode mock data
│   ├── forms.py              # Django forms
│   ├── urls.py               # frontend routes
│   ├── views.py              # page controllers
│   ├── templates/ui/         # HTML templates
│   └── static/ui/styles.css  # CSS
├── k8s/                      # Kubernetes deployment 範例
├── Dockerfile
├── requirements.txt
├── .env.example
└── manage.py
```

## 本機啟動

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

開啟：

```text
http://127.0.0.1:8000/login/
```

Demo Mode 預設開啟，任意帳密都可登入。

## 串接 FastAPI

修改 `.env`：

```env
BACKEND_API_URL=http://localhost:8000/api
DEMO_MODE=False
```

預期後端 API 路徑：

| UI 功能 | FastAPI Endpoint |
|---|---|
| 註冊 | `POST /api/auth/register` |
| 登入 | `POST /api/auth/login` |
| 目前使用者 | `GET /api/auth/me` |
| Job 清單 | `GET /api/jobs` |
| 建立 Job | `POST /api/jobs` |
| 查詢 Job | `GET /api/jobs/{job_id}` |
| 更新 Job | `PUT /api/jobs/{job_id}` |
| 刪除 Job | `DELETE /api/jobs/{job_id}` |
| 手動執行 | `POST /api/jobs/{job_id}/run` |
| 執行紀錄 | `GET /api/job-runs` |
| Log | `GET /api/job-runs/{run_id}/logs` |
| Retry | `POST /api/job-runs/{run_id}/retry` |
| 健康檢查 | `GET /api/health` |

## Docker Build

```bash
docker build -t django-scheduler-frontend:latest .
docker run --rm -p 8000:8000 --env-file .env django-scheduler-frontend:latest
```

## Kubernetes 部署

請先建立 namespace 和 secret：

```bash
kubectl create namespace job-scheduler
kubectl -n job-scheduler create secret generic django-frontend-secret \
  --from-literal=secret-key='replace-this-secret-key'
```

修改 `k8s/django-frontend-deployment.yaml` 內的 image、host、BACKEND_API_URL 後部署：

```bash
kubectl apply -f k8s/django-frontend-deployment.yaml
```

## 分工對應

此專案主要對應政卿的 UI / 支援整合模組，可串接：

- 其佑：FastAPI Auth、Job API、Route
- 杰霖：Job Runs、Logs、DB Controller 對應 API
- 振元：Job Controller 回報的執行狀態與 Retry
- 睿謙：K8s 部署、Ingress、Prometheus / Grafana 入口
