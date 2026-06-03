import time

from app.presentation.controllers.scheduler_controller import scan_due_jobs
from app.core.config import get_settings
from app.infrastructure.database.database import SessionLocal, init_db
from app.core.logger import logger

settings = get_settings()


def main():
    init_db()
    logger.info("started")
    while True:
        db = SessionLocal()
        try:
            result = scan_due_jobs(db)
            if result["created_runs"]:
                logger.info(f"created runs: {result['run_ids']}")
        except Exception as exc:
            logger.error(f"error: {exc}")
        finally:
            db.close()

        time.sleep(settings.scheduler_poll_interval_seconds)


if __name__ == "__main__":
    main()
