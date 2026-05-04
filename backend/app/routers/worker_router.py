from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.controllers.queue_controller import dequeue_next_run, finish_run, heartbeat
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.job_run_schema import StatusUpdateRequest

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("")
def list_workers(_: User = Depends(get_current_user)):
    return [{"worker_id": "worker-demo", "status": "running"}]


@router.post("/pull")
def pull_task(worker_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = dequeue_next_run(db, worker_id)
    if not run:
        return {"task": None}
    return {
        "task": {
            "run_id": run.id,
            "job_id": run.job_id,
            "status": run.status,
            "action_type": run.action_type,
            "action_payload": run.action_payload or {},
            "timeout_seconds": run.timeout_seconds,
            "retry_count": run.retry_count,
        }
    }


@router.post("/{run_id}/heartbeat")
def run_heartbeat(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    run = heartbeat(db, run_id)
    return {"status": run.status if run else "not_found"}


@router.post("/{run_id}/finish")
def run_finish(
    run_id: str,
    payload: StatusUpdateRequest | None = Body(default=None),
    status: str | None = None,
    stdout: str | None = None,
    stderr: str | None = None,
    error_message: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    final_status = payload.status if payload else status
    if not final_status:
        raise HTTPException(status_code=400, detail="status is required")
    run = finish_run(
        db,
        run_id,
        final_status,
        payload.error_message if payload else error_message,
        stdout=payload.stdout if payload else stdout,
        stderr=payload.stderr if payload else stderr,
    )
    return {"status": run.status if run else "not_found"}
