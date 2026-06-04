import asyncio
import time
import httpx
from sqlalchemy.orm import Session
from app.infrastructure.database.database import SessionLocal, init_db
from app.domain.entities.job_run import JobRun
from app.presentation.controllers.queue_controller import finish_run
from app.core.logger import logger
from app.services.schedule_utils import utcnow

async def poll_awaiting_runs():
    db = SessionLocal()
    try:
        # 1. Find all runs waiting for external results
        awaiting_runs = db.query(JobRun).filter(JobRun.status == "awaiting_result").all()
        
        for run in awaiting_runs:
            external_id = run.metadata_json.get("external_id")
            if not external_id:
                logger.error(f"Run {run.id} is awaiting_result but has no external_id")
                continue
            
            # 2. Get status_url from payload
            status_url_template = run.action_payload.get("status_url")
            if not status_url_template:
                logger.error(f"Run {run.id} missing status_url in payload")
                continue
            
            status_url = status_url_template.format(external_id=external_id)
            
            # 3. Call external API to check status
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(status_url)
                    if response.status_code == 200:
                        data = response.json()
                        ext_status = data.get("status", "").lower()
                        
                        if ext_status in ("completed", "success", "done"):
                            logger.info(f"External job {external_id} completed. Finishing run {run.id}")
                            finish_run(db, run.id, "success", None, stdout=response.text)
                        elif ext_status in ("failed", "error"):
                            logger.info(f"External job {external_id} failed. Finishing run {run.id}")
                            finish_run(db, run.id, "failed", data.get("error", "External failure"), stderr=response.text)
                        # If still 'running' or 'pending', we just leave it for the next poll
            except Exception as e:
                logger.error(f"Error polling status for run {run.id}: {e}")
                
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
