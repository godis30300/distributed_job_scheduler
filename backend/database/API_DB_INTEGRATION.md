# Backend API Server 與 PostgreSQL 串接說明

本文件給 Backend API Server / Scheduler / Worker 串接 PostgreSQL 使用。DB 設計對應作業題目「Distributed Asynchronous Job Scheduler」：任務註冊、排程派發、執行結果回報、log 查詢、手動重試、水平擴展、故障轉移、任務相依性、長時間任務 heartbeat。

## 1. 連線設定

Docker Compose 內部服務使用：

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/jobscheduler
```

本機直接連 PostgreSQL 使用：

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/jobscheduler
```

初始化資料庫：

```powershell
Get-Content -Raw backend\database\schema.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\seed.sql | docker compose exec -T db psql -U postgres -d jobscheduler
```

既有資料庫升級請依序套 migration：

```powershell
Get-Content -Raw backend\database\migrations\002_db_integration_fields.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\migrations\003_postgresql_queue_integrity.sql | docker compose exec -T db psql -U postgres -d jobscheduler
```

## 2. Table 分工

| Table | 用途 | 主要欄位 |
|---|---|---|
| `users` | API 登入使用者與任務建立者 | `id`, `username`, `email`, `password_hash`, `role` |
| `jobs` | 任務定義與排程規則 | `task_name`, `action_type`, `action_payload`, `schedule_rule`, `enabled`, `status`, `next_run_at`, `timeout_seconds`, `max_retry` |
| `job_runs` | 每一次任務執行紀錄，也是 worker queue | `job_id`, `status`, `trigger_type`, `worker_id`, `locked_by`, `locked_until`, `heartbeat_at`, `retry_count`, `stdout`, `stderr`, `error_message` |
| `job_logs` | 執行過程 log | `job_run_id`, `log_level`, `stream`, `message`, `created_at` |
| `job_dependencies` | Job 執行順序相依 | `job_id`, `depends_on_job_id`, `required_status` |

## 3. API 動作對應 DB

| API / Component | DB 行為 |
|---|---|
| `POST /api/jobs` | 新增 `jobs`，寫入 `action_type/action_payload/schedule_rule` |
| `GET /api/jobs` | 查詢 `jobs`，可依 `status` 或 keyword 過濾 |
| `PUT /api/jobs/{job_id}` | 更新 `jobs`，DB trigger 會更新 `updated_at` |
| `DELETE /api/jobs/{job_id}` | soft delete：`status='deleted'`, `enabled=false`, `next_run_at=null` |
| `POST /api/jobs/{job_id}/trigger` | 新增一筆 `job_runs(status='pending', trigger_type='manual')` |
| Scheduler scan | 查 `jobs.next_run_at <= now()`，建立 `job_runs(status='pending', trigger_type='schedule')` |
| Worker pull | 使用 `FOR UPDATE SKIP LOCKED` 鎖定一筆 pending run，改成 `running` |
| Worker heartbeat | 更新 `job_runs.heartbeat_at`，避免長時間任務被誤判過期 |
| Worker finish | 更新 `status/end_time/stdout/stderr/error_message`，DB trigger 會計算 `duration_seconds` |
| Retry | 新增一筆 `job_runs(trigger_type='retry', retry_count=上一筆+1)` |
| Log search | 查 `job_logs` 或 view `v_job_run_log_search` |

## 4. Job Payload 格式

API 建立 job 時可使用作業需求中的 REST API / shell 類型。

REST API job：

```json
{
  "task_name": "daily-report-api",
  "schedule_type": "cron",
  "cron_expression": "0 2 * * *",
  "action": "api_call",
  "action_payload": {
    "method": "POST",
    "url": "https://example.com/reports/daily",
    "headers": {},
    "body": {}
  },
  "timeout_seconds": 300,
  "retry_limit": 3
}
```

Shell job：

```json
{
  "task_name": "backup-database",
  "schedule_type": "interval",
  "interval_seconds": 600,
  "action": "shell",
  "action_payload": {
    "script": "hello.sh",
    "args": []
  },
  "timeout_seconds": 600,
  "retry_limit": 2
}
```

DB 內實際儲存為：

| API 欄位 | DB 欄位 |
|---|---|
| `action` | `jobs.action_type` |
| `action_payload` | `jobs.action_payload` |
| `schedule_type=manual` | `jobs.schedule_rule='manual'` |
| `schedule_type=interval`, `interval_seconds=300` | `jobs.schedule_rule='every:300s'` |
| `schedule_type=cron`, `cron_expression='0 2 * * *'` | `jobs.schedule_rule='0 2 * * *'` |
| `retry_limit` | `jobs.max_retry` |

## 5. Worker Queue Lock

多個 worker 可以同時呼叫 pull。PostgreSQL 會用 row-level lock 分配不同任務，避免同一個 job run 被重複執行。

```sql
SELECT jr.*
FROM job_runs jr
JOIN jobs j ON j.id = jr.job_id
WHERE jr.status = 'pending'
  AND j.enabled = TRUE
  AND j.status IN ('enabled', 'active')
ORDER BY jr.created_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

鎖到任務後要立刻更新：

```sql
UPDATE job_runs
SET status = 'running',
    worker_id = :worker_id,
    locked_by = :worker_id,
    locked_until = now() + make_interval(secs => :lock_seconds),
    start_time = COALESCE(start_time, now()),
    heartbeat_at = now()
WHERE id = :run_id;
```

## 6. 故障轉移與長時間任務

Worker 執行中要定期更新：

```sql
UPDATE job_runs
SET heartbeat_at = now()
WHERE id = :run_id
  AND status = 'running';
```

如果 worker 掛掉，queue controller 可釋放過期 lock：

```sql
UPDATE job_runs
SET status = 'pending',
    worker_id = NULL,
    locked_by = NULL,
    locked_until = NULL,
    heartbeat_at = now()
WHERE status = 'running'
  AND locked_until < now();
```

## 7. Log 與查詢

每次 worker 執行過程都寫入 `job_logs`：

```sql
INSERT INTO job_logs (id, job_run_id, log_level, stream, message)
VALUES (:uuid, :run_id, 'info', 'stdout', 'job started');
```

後端查詢 log 可直接查 view：

```sql
SELECT *
FROM v_job_run_log_search
WHERE task_name = 'daily-report-api'
  AND run_status = 'failed'
ORDER BY log_created_at DESC
LIMIT 100;
```

## 8. 對應作業需求檢查

| 作業需求 | DB 支援方式 |
|---|---|
| 任務註冊與管理 | `jobs` table + API CRUD |
| 執行內容 | `jobs.action_type`, `jobs.action_payload` |
| 排程規則 | `jobs.schedule_rule`, `jobs.next_run_at` |
| 任務派發 | `job_runs` 作為 queue |
| 執行結果回報 | `job_runs.status/stdout/stderr/error_message/duration_seconds` |
| Log 寫入 DB | `job_logs` + `v_job_run_log_search` |
| 手動觸發/重試 | `trigger_type='manual'/'retry'`, `retry_count` |
| 水平擴展 | `FOR UPDATE SKIP LOCKED` + pending queue index |
| 故障轉移 | `locked_until`, `heartbeat_at`, release expired locks |
| 任務相依性 | `job_dependencies.required_status` |
| 長時間任務 | heartbeat + lock lease |
