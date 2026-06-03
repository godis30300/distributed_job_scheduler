import asyncio
import os
import time

from app.controllers.queue_controller import add_log, dequeue_next_run, finish_run
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.services.executor import execute_job

settings = get_settings()


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
            action_payload = run.action_payload if run.action_payload is not None else job.action_payload
            action_payload = dict(action_payload or {})
            if run.script is not None:
                action_payload["script"] = run.script
            if run.working_dir is not None:
                action_payload["working_dir"] = run.working_dir
            timeout_seconds = run.timeout_seconds or job.timeout_seconds
            task_type = run.task_type or run.action_type
            add_log(db, run.id, "INFO", f"Start executing job: {job.task_name} ({task_type})")
            print(f"[worker] executing run {run.id}: {job.task_name}")

            result = asyncio.run(execute_job(task_type, action_payload, timeout_seconds))

            stderr = result.get("stderr") or ""
            finish_status = "success" if result.get("success") else "failed"
            if stderr.startswith("timeout after"):
                finish_status = "timeout"

            print(f"[worker] finished run {run.id}: {finish_status}")
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
