import asyncio
import httpx
from datetime import timezone
from app.infrastructure.database.database import SessionLocal, init_db
from app.domain.entities.job_run import JobRun
from app.presentation.controllers.queue_controller import finish_run
from app.core.logger import logger
from app.services.schedule_utils import utcnow

def _is_timed_out(run: JobRun, now) -> bool:
    reference = run.start_time or run.created_at
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return (now - reference).total_seconds() > run.timeout_seconds


async def _poll_external(db, run: JobRun) -> None:
    external_id = (run.metadata_json or {}).get("external_id")
    if not external_id:
        logger.error(f"run {run.id} is awaiting_result but has no external_id")
        return

    status_url_template = (run.action_payload or {}).get("status_url")
    if not status_url_template:
        logger.error(f"run {run.id} missing status_url in payload")
        return

    status_url = status_url_template.format(external_id=external_id)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(status_url)
        if response.status_code != 200:
            return
        ext_status = response.json().get("status", "").lower()
        if ext_status in ("completed", "success", "done"):
            logger.info(f"external job {external_id} completed, finishing run {run.id}")
            finish_run(db, run.id, "success", None, stdout=response.text)
        elif ext_status in ("failed", "error"):
            logger.info(f"external job {external_id} failed, finishing run {run.id}")
            finish_run(db, run.id, "failed", response.json().get("error", "External failure"), stderr=response.text)
        # still running/pending → wait for next poll
    except Exception as e:
        logger.error(f"error polling status for run {run.id}: {e}")


async def poll_awaiting_runs():
    db = SessionLocal()
    try:
        awaiting_runs = db.query(JobRun).filter(JobRun.status == "awaiting_result").all()
        now = utcnow()
        for run in awaiting_runs:
            if _is_timed_out(run, now):
                elapsed = (now - (run.start_time or run.created_at)).total_seconds()
                logger.warning(f"run {run.id} awaiting_result timed out after {elapsed:.0f}s")
                finish_run(db, run.id, "timeout", f"awaiting_result timed out after {elapsed:.0f}s")
            else:
                await _poll_external(db, run)
    finally:
        db.close()

async def main():
    init_db()
    logger.info("Status Poller started")
    while True:
        try:
            await poll_awaiting_runs()
        except Exception as e:
            logger.error(f"Poller loop error: {e}")
        
        await asyncio.sleep(60) # Poll every 60 seconds

if __name__ == "__main__":
    asyncio.run(main())
