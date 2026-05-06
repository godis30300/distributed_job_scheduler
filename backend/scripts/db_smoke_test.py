from __future__ import annotations  # 讓型別註解延後解析，避免某些型別在執行時先被求值。

import sys  # 用來修改 Python import 路徑，最後也用 sys.exit() 回傳測試結果代碼。
from datetime import datetime, timezone  # 用來建立固定時間，讓測試 job_run 可以排在 pending queue 最前面。
from pathlib import Path  # 用來計算 backend 專案根目錄的位置。

# 這個檔案放在 backend/scripts，直接執行時 Python 只會把 scripts 加到 import path。
BACKEND_ROOT = Path(__file__).resolve().parents[1]  # 取得 backend 目錄，例如 /app。

# 如果 backend 目錄不在 import path，補進去，這樣才能 import app.controllers / app.models。
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))  # 把 backend 目錄放在最前面，優先使用本專案程式碼。

from sqlalchemy import text  # 用來執行簡單 SQL，例如查 information_schema 和 COUNT(*)。
from sqlalchemy.exc import SQLAlchemyError  # 用來捕捉資料庫連線或 SQLAlchemy 初始化錯誤。

from app.controllers.job_run_controller import search_job_logs  # 測試 log 搜尋 controller 是否能用。
from app.controllers.queue_controller import finish_run, lock_pending_job  # 測試 worker 鎖任務與完成任務流程。
from app.core.database import SessionLocal, init_db  # init_db 建表，SessionLocal 建立 DB session。
from app.models.job import Job  # 測試建立 jobs 表資料。
from app.models.job_log import JobLog  # 測試查詢 job_logs 表資料。
from app.models.job_run import JobRun  # 測試建立 job_runs 表資料。
from app.models.user import User  # 測試建立 users 表資料。


SMOKE_USERNAME = "db_smoke_user"  # smoke test 專用使用者名稱，重跑測試會重用這個 user。
SMOKE_EMAIL = "db-smoke@example.com"  # smoke test 專用 email，方便人工辨識測試資料。
SMOKE_JOB_NAME = "db-smoke-shell-job"  # smoke test 專用 job 名稱，重跑前會刪掉舊 job 避免 unique 衝突。
SMOKE_WORKER_ID = "db-smoke-worker"  # 模擬 worker 名稱，用來測 locked_by / worker_id 是否寫入 DB。


# 這份清單定義每張表必須存在的欄位；少任何欄位都代表 schema 沒套成功。
REQUIRED_COLUMNS = {
    "users": {  # users 表：驗證 auth 使用者資料欄位。
        "id",  # 使用者 UUID。
        "username",  # 登入帳號。
        "email",  # email，可為空。
        "password_hash",  # 密碼 hash，不存明文密碼。
        "role",  # 使用者角色。
        "created_at",  # 建立時間。
    },
    "jobs": {  # jobs 表：驗證任務定義欄位。
        "id",  # job UUID。
        "user_id",  # 建立 job 的使用者。
        "task_name",  # 任務名稱，DB 有 unique constraint。
        "action_type",  # 任務種類，例如 shell/api_call/report。
        "action_payload",  # 任務參數 JSON。
        "schedule_rule",  # 排程規則，例如 manual/every:5m/cron。
        "status",  # 任務狀態，例如 enabled/disabled/deleted。
        "enabled",  # 是否啟用。
        "timeout_seconds",  # timeout 秒數。
        "max_retry",  # 最大重試次數。
        "next_run_at",  # 下一次排程執行時間。
        "created_at",  # 建立時間。
        "updated_at",  # 更新時間。
    },
    "job_runs": {  # job_runs 表：驗證每次執行紀錄欄位。
        "id",  # run UUID。
        "job_id",  # 對應 jobs.id。
        "user_id",  # 觸發 run 的使用者。
        "status",  # pending/running/success/failed/timeout/canceled。
        "trigger_type",  # schedule/manual/retry。
        "triggered_by",  # 誰觸發，例如 manual/db-smoke-test。
        "worker_id",  # 哪個 worker 執行。
        "locked_by",  # 哪個 worker 鎖住這筆 run。
        "locked_until",  # 鎖定到期時間。
        "start_time",  # 執行開始時間。
        "end_time",  # 執行結束時間。
        "duration_seconds",  # 執行花費秒數。
        "retry_count",  # 第幾次重試。
        "action_type",  # run 建立當下的 action 快照。
        "action_payload",  # run 建立當下的 payload 快照。
        "timeout_seconds",  # run 建立當下的 timeout 快照。
        "stdout",  # 執行 stdout。
        "stderr",  # 執行 stderr。
        "error_message",  # 錯誤訊息。
        "created_at",  # 建立時間。
        "updated_at",  # 更新時間。
    },
    "job_logs": {  # job_logs 表：驗證 log viewer 需要的欄位。
        "id",  # log UUID。
        "job_run_id",  # 對應 job_runs.id。
        "log_level",  # debug/info/warning/error。
        "stream",  # stdout/stderr/system。
        "message",  # log 內容。
        "created_at",  # log 建立時間。
    },
    "job_dependencies": {  # job_dependencies 表：驗證任務相依性欄位。
        "id",  # dependency UUID。
        "job_id",  # 需要等待的 job。
        "depends_on_job_id",  # 前置 job。
        "required_status",  # 前置 job 需要達到的狀態，預設 success。
        "created_at",  # 建立時間。
    },
}


def step(message: str) -> None:
    """印出目前測試步驟，讓終端輸出比較容易讀。"""
    print(f"[db-smoke] {message}")  # 成功流程會一直看到 [db-smoke] 開頭的進度訊息。


def require(condition: bool, message: str) -> None:
    """像簡單 assert；條件不成立就讓測試失敗。"""
    if not condition:  # 如果條件是 False，代表某個 DB 行為不符合預期。
        raise AssertionError(message)  # 丟出 AssertionError，main() 會印 DB SMOKE TEST FAILED。


def check_schema(db) -> None:
    """檢查 DB 是否有必要資料表與欄位。"""
    rows = db.execute(  # 對目前連線的 PostgreSQL 執行 SQL。
        text(  # text() 讓 SQLAlchemy 執行原生 SQL 字串。
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name IN ('users', 'jobs', 'job_runs', 'job_logs', 'job_dependencies')
            """
        )
    ).all()  # all() 取回所有 table_name / column_name 結果。

    actual: dict[str, set[str]] = {}  # 存實際 DB 裡每張表有哪些欄位。
    for table_name, column_name in rows:  # 逐筆整理 SQL 查到的欄位。
        actual.setdefault(table_name, set()).add(column_name)  # 例如 actual["jobs"].add("task_name")。

    missing: list[str] = []  # 存缺少的表或欄位，最後一次印出。
    for table_name, columns in REQUIRED_COLUMNS.items():  # 逐張表比對必要欄位。
        if table_name not in actual:  # 如果整張表不存在。
            missing.append(f"{table_name}: table missing")  # 記錄缺少表。
            continue  # 表不存在就不用再比對欄位。
        missing_columns = sorted(columns - actual[table_name])  # 用集合相減找出缺少欄位。
        if missing_columns:  # 如果有缺欄位。
            missing.append(f"{table_name}: missing {', '.join(missing_columns)}")  # 記錄缺少欄位。

    if missing:  # 只要有缺表或缺欄位，就代表 schema 沒套好。
        details = "\n  - ".join(missing)  # 把錯誤整理成多行，方便看。
        raise RuntimeError(  # 丟出明確錯誤，讓 main() 顯示失敗原因。
            "Database schema is not up to date.\n"  # 說明 DB schema 不是最新版。
            f"  - {details}\n"  # 列出缺少哪些表或欄位。
            "For a clean local test, run: docker compose down -v ; docker compose up -d db backend"
        )  # 告訴使用者如何重建乾淨 DB。


def clean_previous_smoke_data(db) -> None:
    """刪除上一輪 smoke test 建立的 job，避免 task_name unique 衝突。"""
    old_job = db.query(Job).filter(Job.task_name == SMOKE_JOB_NAME).first()  # 查是否已有舊測試 job。
    if old_job:  # 如果存在舊測試 job。
        db.delete(old_job)  # 刪掉 job；因為 relationship/DB cascade，相關 run/log 也會被清掉。
        db.commit()  # 寫入刪除結果。


def ensure_smoke_user(db) -> User:
    """確保測試用 user 存在；存在就重用，不存在就新增。"""
    user = db.query(User).filter(User.username == SMOKE_USERNAME).first()  # 用 username 找測試 user。
    if user:  # 如果 user 已存在。
        return user  # 直接回傳，避免重複建立同名 user。

    user = User(  # 建立新的測試 user 物件。
        username=SMOKE_USERNAME,  # 寫入測試 username。
        email=SMOKE_EMAIL,  # 寫入測試 email。
        password_hash="db-smoke-not-a-real-password-hash",  # 測 DB 不測登入，所以放假 hash 即可。
        role="operator",  # 給一般 operator 角色。
    )
    db.add(user)  # 把 user 加到 session，準備 INSERT。
    db.commit()  # 寫入 users 表。
    db.refresh(user)  # 從 DB 取回 id/created_at 等欄位。
    return user  # 回傳剛建立的 user。


def create_smoke_job_and_run(db, user: User) -> tuple[Job, JobRun]:
    """建立一個 manual shell job，並建立一筆 pending job_run。"""
    job = Job(  # 建立 jobs 表資料，代表一個任務定義。
        user_id=user.id,  # 指定任務建立者。
        task_name=SMOKE_JOB_NAME,  # 使用固定測試 job 名稱。
        action_type="shell",  # 測 shell action。
        action_payload={"script": "hello.sh", "args": []},  # 指定執行 backend/scripts/hello.sh。
        schedule_rule="manual",  # manual 表示不靠排程，自行建立 run。
        status="enabled",  # job 狀態為啟用。
        enabled=True,  # enabled 欄位也設 true。
        timeout_seconds=30,  # 設定 timeout 秒數。
        max_retry=1,  # 設定最多重試 1 次。
        description="DB smoke test job; safe to delete",  # 說明這是測試資料。
    )
    db.add(job)  # 把 job 加到 session。
    db.commit()  # 寫入 jobs 表。
    db.refresh(job)  # 從 DB 取回 job.id。

    run = JobRun(  # 建立 job_runs 表資料，代表一次任務執行。
        job_id=job.id,  # 指向剛建立的 job。
        user_id=user.id,  # 指向測試 user。
        status="pending",  # 初始狀態 pending，等待 worker/lock 取得。
        trigger_type="manual",  # 模擬手動觸發。
        triggered_by="db-smoke-test",  # 標記來源是這支測試腳本。
        retry_count=0,  # 第一次執行，不是 retry。
        action_type=job.action_type,  # 複製 job.action_type 當 run snapshot。
        action_payload=job.action_payload,  # 複製 job.action_payload 當 run snapshot。
        timeout_seconds=job.timeout_seconds,  # 複製 job.timeout_seconds 當 run snapshot。
        created_at=datetime(2000, 1, 1, tzinfo=timezone.utc),  # 固定早時間，確保 lock_pending_job 先抓到這筆。
    )
    db.add(run)  # 把 run 加到 session。
    db.commit()  # 寫入 job_runs 表。
    db.refresh(run)  # 從 DB 取回 run.id。
    return job, run  # 回傳 job 和 run，後續測試會用到 id。


def print_table_counts(db) -> None:
    """印出主要資料表目前筆數，用來確認測試前後資料有增加。"""
    for table_name in ("users", "jobs", "job_runs", "job_logs", "job_dependencies"):  # 逐張主要表查筆數。
        count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()  # 執行 COUNT(*)。
        step(f"{table_name}: {count} rows")  # 印出例如 users: 3 rows。


def main() -> int:
    """執行完整 DB smoke test；成功回傳 0，失敗回傳 1。"""
    try:  # 第一段先測 DB 是否能連線。
        init_db()  # 匯入 models 並呼叫 create_all；如果表不存在會嘗試建立。
        db = SessionLocal()  # 建立一個 SQLAlchemy DB session。
    except SQLAlchemyError as exc:  # 如果連線或初始化 DB 失敗。
        print("[db-smoke] Cannot connect to database.")  # 失敗輸出：告訴你連不到 DB。
        print(f"[db-smoke] {exc}")  # 失敗輸出：印出 SQLAlchemy 原始錯誤。
        print("[db-smoke] Make sure db/backend are running: docker compose up -d db backend")  # 失敗輸出：提示啟動方式。
        return 1  # 回傳 1，代表測試失敗。

    try:  # 第二段開始跑實際 DB 功能測試。
        step("checking required tables and columns")  # 成功流程輸出：開始檢查 schema。
        check_schema(db)  # 檢查 5 張表和必要欄位是否存在。

        step("current table counts")  # 成功流程輸出：列出測試前資料量。
        print_table_counts(db)  # 印出 users/jobs/job_runs/job_logs/job_dependencies 筆數。

        step("creating smoke user/job/job_run")  # 成功流程輸出：開始建立測試資料。
        clean_previous_smoke_data(db)  # 先刪舊測試 job，避免 task_name unique 衝突。
        user = ensure_smoke_user(db)  # 確保測試 user 存在。
        job, run = create_smoke_job_and_run(db, user)  # 建立測試 job 和 pending run。
        step(f"created job={job.id} run={run.id}")  # 成功流程輸出：印出剛建立的 id。

        step("locking one pending run with FOR UPDATE SKIP LOCKED")  # 成功流程輸出：開始測 queue lock。
        locked_run = lock_pending_job(db, SMOKE_WORKER_ID, lock_seconds=60)  # 模擬 worker 鎖定 pending run。
        require(locked_run is not None, "expected one pending run to be locked")  # 確認有抓到 run。
        require(locked_run.id == run.id, f"locked unexpected run: {locked_run.id}")  # 確認抓到的是剛建立的 run。
        require(locked_run.status == "running", "locked run should be running")  # 確認 status 已改 running。
        require(locked_run.locked_by == SMOKE_WORKER_ID, "locked_by was not saved")  # 確認 locked_by 已寫入。
        step(f"locked run={locked_run.id} worker={locked_run.locked_by}")  # 成功流程輸出：印出被鎖定的 run 和 worker。

        step("finishing run and saving stdout/stderr/logs")  # 成功流程輸出：開始測完成任務和寫 log。
        finished_run = finish_run(  # 呼叫 queue_controller.finish_run 模擬 worker 執行完成。
            db,  # 傳入 DB session。
            locked_run.id,  # 指定剛剛鎖到的 run。
            "success",  # 把 run 狀態改成 success。
            stdout="db smoke stdout",  # 模擬任務 stdout。
            stderr="",  # 模擬沒有 stderr。
        )
        require(finished_run is not None, "finish_run returned None")  # 確認 run 存在且有更新。
        require(finished_run.status == "success", "finished run should be success")  # 確認狀態是 success。
        require(finished_run.stdout == "db smoke stdout", "stdout was not saved")  # 確認 stdout 寫進 job_runs。
        require(finished_run.end_time is not None, "end_time was not saved")  # 確認 end_time 有寫入。

        logs = db.query(JobLog).filter(JobLog.job_run_id == run.id).order_by(JobLog.created_at.asc()).all()  # 查這次 run 的 logs。
        require(logs, "expected job_logs rows for the smoke run")  # 確認至少有 log。
        require(any(log.stream == "stdout" for log in logs), "stdout log was not saved")  # 確認 stdout log 有寫入 job_logs。
        require(any("Run finished: success" in log.message for log in logs), "finish system log was not saved")  # 確認完成訊息有寫入。
        step(f"saved {len(logs)} logs for run={run.id}")  # 成功流程輸出：印出 log 筆數。

        step("testing search_job_logs(task_name/status)")  # 成功流程輸出：開始測 log 查詢功能。
        search_results = search_job_logs(db, task_name=SMOKE_JOB_NAME, status="success", limit=20)  # 依任務名稱和狀態搜尋 log。
        require(any(log.job_run_id == run.id for log in search_results), "search_job_logs did not find smoke logs")  # 確認搜尋結果包含本次 run。

        step("final table counts")  # 成功流程輸出：列出測試後資料量。
        print_table_counts(db)  # 印出測試後各表筆數。

        print("\nDB SMOKE TEST PASSED")  # 成功輸出：看到這行代表整個 DB smoke test 通過。
        print(f"Smoke job name: {SMOKE_JOB_NAME}")  # 成功輸出：告訴你測試 job 名稱，方便手動查 DB。
        print(f"Smoke run id:   {run.id}")  # 成功輸出：告訴你測試 run id，方便查 job_runs/job_logs。
        return 0  # 回傳 0，代表測試成功。
    except Exception as exc:  # 任何測試步驟失敗都會進來。
        db.rollback()  # 回滾尚未 commit 的 DB 操作，避免半套資料。
        print("\nDB SMOKE TEST FAILED")  # 失敗輸出：看到這行代表測試沒通過。
        print(f"{type(exc).__name__}: {exc}")  # 失敗輸出：印出錯誤類型和原因，例如 AssertionError/RuntimeError。
        return 1  # 回傳 1，代表測試失敗。
    finally:  # 無論成功或失敗都會執行。
        db.close()  # 關閉 DB session，釋放連線。


if __name__ == "__main__":  # 只有直接執行 python scripts/db_smoke_test.py 時才會跑。
    sys.exit(main())  # 執行 main()，並把 0/1 結果回傳給 shell 或 Docker。
