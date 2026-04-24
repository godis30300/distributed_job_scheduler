import time

from app.controllers.scheduler_controller import scan_due_jobs
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db

settings = get_settings()


def main():
    init_db()
    print("[scheduler] started")
    while True:
        db = SessionLocal()
        try:
            result = scan_due_jobs(db)
            if result["created_runs"]:
                print(f"[scheduler] created runs: {result['run_ids']}")
        except Exception as exc:
            print(f"[scheduler] error: {exc}")
        finally:
            db.close()

        time.sleep(settings.scheduler_poll_interval_seconds)


if __name__ == "__main__":
    main()
