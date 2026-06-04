import asyncio
import os
import json
import select
from datetime import datetime, timezone

from app.presentation.controllers.queue_controller import add_log, dequeue_next_run, finish_run
from app.core.config import get_settings
from app.infrastructure.database.database import SessionLocal, init_db
from app.core.logger import logger
from app.application.services.executor import execute_job

settings = get_settings()

# Configuration for concurrency
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))
POLL_INTERVAL = settings.worker_poll_interval_seconds

# Semaphore to control concurrency within this Pod
semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


async def run_job_task(worker_id: str, run_id: str = None):
    """
    Independent task to handle a single job execution.
    If run_id is None, it will try to dequeue one from the DB.
    """
    async with semaphore:
        db = SessionLocal()
        try:
            # 1. Dequeue / Lock
            run = dequeue_next_run(db, worker_id)
            if not run:
                return

            job = run.job
            # Prepare payload
            action_payload = run.action_payload if run.action_payload is not None else job.action_payload
            action_payload = dict(action_payload or {})
            if run.script is not None:
                action_payload["script"] = run.script
            if run.working_dir is not None:
                action_payload["working_dir"] = run.working_dir
            
            timeout_seconds = run.timeout_seconds or job.timeout_seconds
            task_type = run.task_type or run.action_type

            add_log(db, run.id, "INFO", f"Start executing job: {job.task_name} ({task_type})")
            logger.info(f"executing run {run.id}: {job.task_name}")

            # 2. Execute
            result = await execute_job(task_type, action_payload, timeout_seconds)

            # 3. Handle Result
            if result.get("status") == "awaiting":
                # Special Case: Async Long-Running Job
                logger.info(f"run {run.id} entered awaiting_result status (ext_id: {result.get('external_id')})")
                run.status = "awaiting_result"
                run.metadata_json = {"external_id": result.get("external_id")}
                run.stdout = result.get("stdout")
                db.commit()
                return # RELEASE SEMAPHORE AND EXIT

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
            logger.error(f"error in task for run {run.id if 'run' in locals() and run else 'unknown'}: {exc}")
        finally:
            db.close()


async def event_listener(worker_id: str, trigger_event: asyncio.Event):
    """
    Coroutine that uses a dedicated connection to LISTEN for DB notifications.
    """
    logger.info("event listener started")
    db = SessionLocal()
    conn = db.bind.raw_connection()
    conn.set_isolation_level(0) # autocommit
    cursor = conn.cursor()
    cursor.execute("LISTEN job_run_events;")

    try:
        while True:
            # Use select to wait for data on the connection without blocking the event loop
            if select.select([conn], [], [], 5) == ([], [], []):
                # Timeout, just loop again
                pass
            else:
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    # print(f"[worker] received notification: {notify.payload}")
                    trigger_event.set() # Wake up the queue checker
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"event listener crashed: {e}")
    finally:
        cursor.close()
        conn.close()
        db.close()


async def worker_main():
    init_db()
    worker_id = os.getenv("WORKER_ID", settings.worker_id)
    logger.info(f"started: {worker_id} (concurrency: {MAX_CONCURRENT_JOBS})")

    # Signal to wake up and check the DB queue
    trigger_event = asyncio.Event()
    trigger_event.set() # Start with a check

    # Start the DB listener in the background
    asyncio.create_task(event_listener(worker_id, trigger_event))

    while True:
        try:
            # Wait for either a notification or periodic poll
            try:
                await asyncio.wait_for(trigger_event.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass # Periodic poll
            
            trigger_event.clear()

            # Try to start as many jobs as possible until concurrency limit or queue empty
            # We don't want to block the loop, so we create tasks.
            # Semaphore inside run_job_task will handle the limit.
            
            # Since we can't easily peek the queue without locking, we just try to spawn
            # a few dequeue attempts.
            for _ in range(MAX_CONCURRENT_JOBS):
                # Only spawn if we haven't reached concurrency limit
                if semaphore.locked():
                    break
                asyncio.create_task(run_job_task(worker_id))
                
        except Exception as exc:
            logger.error(f"main loop error: {exc}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(worker_main())
