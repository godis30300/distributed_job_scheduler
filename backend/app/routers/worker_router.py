from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.controllers.queue_controller import dequeue_next_run, finish_run, heartbeat
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("")
def list_workers(_: User = Depends(get_current_user)):
    return [{"worker_id": "worker-demo", "status": "running"}]


@router.post("/pull")
def pull_task(worker_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = dequeue_next_run(db, worker_id)
    if not run:
        return {"task": None}
    return {"run_id": run.id, "job_id": run.job_id, "status": run.status}


@router.post("/{run_id}/heartbeat")
def run_heartbeat(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = heartbeat(db, run_id)
    return {"status": run.status if run else "not_found"}


@router.post("/{run_id}/finish")
def run_finish(
    run_id: str,
    status: str,
    error_message: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    run = finish_run(db, run_id, status, error_message)
    return {"status": run.status if run else "not_found"}
