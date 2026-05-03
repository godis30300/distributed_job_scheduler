import asyncio
import os
import time

from app.controllers.queue_controller import add_log, dequeue_next_run, finish_run
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.services.executor import execute_job

settings = get_settings()


async def execute_one_run(run_id: str, job, timeout_seconds: int):
    result = await execute_job(job.action_type, job.action_payload, timeout_seconds)
    return result


def main():
    init_db()
    worker_id = os.getenv("WORKER_ID", settings.worker_id)
    print(f"[worker] started: {worker_id}")

    while True:
        db = SessionLocal()
        try:
            run = dequeue_next_run(db, worker_id)
            if not run:
                db.close()
                time.sleep(settings.worker_poll_interval_seconds)
                continue

            job = run.job
            add_log(db, run.id, "INFO", f"Start executing job: {job.task_name}")

            result = asyncio.run(execute_one_run(run.id, job, job.timeout_seconds))

            if result.get("stdout"):
                add_log(db, run.id, "INFO", result["stdout"], stream="stdout")
            if result.get("stderr"):
                add_log(db, run.id, "ERROR", result["stderr"], stream="stderr")

            stderr = result.get("stderr") or ""
            finish_status = "success" if result.get("success") else "failed"
            if stderr.startswith("timeout after"):
                finish_status = "timeout"

            finish_run(
                db,
                run.id,
                finish_status,
                None if result.get("success") else result.get("stderr", "execution failed"),
                stdout=result.get("stdout"),
                stderr=stderr,
            )
        except Exception as exc:
            print(f"[worker] error: {exc}")
        finally:
            db.close()


if __name__ == "__main__":
    main()
