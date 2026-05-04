# PostgreSQL / Log / DB Controller

主要串接文件請看 [API_DB_INTEGRATION.md](API_DB_INTEGRATION.md)。

本目錄是 Distributed Asynchronous Job Scheduler 的資料庫交付範圍，對應作業題目中的任務註冊、排程派發、worker queue、log、結果回報、重試、故障轉移、任務相依性。

# 杰霖｜PostgreSQL / Log / DB Controller

這個資料夾是 Distributed Asynchronous Job Scheduler 的資料庫交付內容，對應 README 分工中的：

```text
backend/app/models/
backend/app/controllers/job_run_controller.py
backend/app/controllers/queue_controller.py
```

## 負責內容

- PostgreSQL schema：`users`、`jobs`、`job_runs`、`job_logs`、`job_dependencies`
- Log 儲存與查詢：依任務、狀態、使用者、時間、log level 查詢
- Job Run Controller：執行紀錄、重試、取消、狀態更新、log 寫入
- Queue Controller：pending job 查詢、任務鎖定、過期鎖釋放、dependency 檢查
- DB index：針對 scheduler、worker、UI 常用查詢建立索引
- PostgreSQL lock：使用 `FOR UPDATE SKIP LOCKED` 防止重複執行

## 資料表

### users

儲存登入與權限資料。欄位包含 `id`、`username`、`password_hash`、`role`、`created_at`。

### jobs

儲存任務定義。欄位包含 `task_name`、`action_type`、`action_payload`、`schedule_rule`、`status`、`timeout_seconds`、`max_retry`、`next_run_at`。

### job_runs

儲存每次任務執行紀錄。欄位包含 `status`、`user_id`、`start_time`、`end_time`、`duration_seconds`、`retry_count`、`locked_by`、`locked_until`、`stdout`、`stderr`、`error_message`。

### job_logs

儲存任務執行 log。支援 `stdout`、`stderr`、`system` 三種 stream。

### job_dependencies

儲存任務相依性，例如 shell cleanup job 要等 health API job 成功後才可執行。

## Queue Lock 設計

`backend/app/controllers/queue_controller.py` 的 `lock_pending_job()` 使用 SQLAlchemy：

```python
.with_for_update(skip_locked=True)
```

等價 SQL：

```sql
SELECT *
FROM job_runs
WHERE status = 'pending'
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

當多個 worker 同時取任務時，已被鎖住的 row 會被其他 worker 跳過，因此同一筆 `job_runs` 不會被重複執行。

## 如何套用 SQL

啟動 docker compose 後：

```powershell
Get-Content -Raw backend\database\schema.sql | docker compose exec -T db psql -U postgres -d jobscheduler
Get-Content -Raw backend\database\seed.sql | docker compose exec -T db psql -U postgres -d jobscheduler
```

## 整合方式

- 其佑 API：呼叫 job / job_run controllers 建立 job、trigger run、retry、cancel
- 振元 worker/scheduler：呼叫 queue controller 鎖定 pending run、寫 log、完成 run
- 政卿 UI：透過 job-runs API 查詢狀態與 logs
- 睿謙部署：PostgreSQL 使用 docker-compose 或 K8s manifests，schema 可作為 init SQL 或 migration 參考
