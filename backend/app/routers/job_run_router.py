from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.controllers import job_run_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.job_run_schema import JobLogResponse, JobRunResponse

router = APIRouter(prefix="/job-runs", tags=["job-runs"])


@router.get("", response_model=list[JobRunResponse])
def list_job_runs(
    status: str | None = Query(default=None),
    job_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return job_run_controller.list_job_runs(
        db,
        status=status,
        user_id=user_id,
        job_id=job_id,
        limit=limit,
        offset=offset,
    )


@router.get("/logs/search", response_model=list[JobLogResponse])
def search_logs(
    task_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    log_level: str | None = Query(default=None),
    start_time_from: datetime | None = Query(default=None),
    start_time_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return job_run_controller.search_job_logs(
        db,
        task_name=task_name,
        status=status,
        user_id=user_id,
        log_level=log_level,
        start_time_from=start_time_from,
        start_time_to=start_time_to,
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}", response_model=JobRunResponse)
def get_job_run(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return job_run_controller.get_run_or_404(db, run_id)


@router.get("/{run_id}/logs", response_model=list[JobLogResponse])
def get_logs(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return job_run_controller.list_logs(db, run_id)


@router.post("/{run_id}/retry", response_model=JobRunResponse)
def retry_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return job_run_controller.retry_run(db, run_id, current_user)


@router.post("/{run_id}/cancel", response_model=JobRunResponse)
def cancel_run(run_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return job_run_controller.cancel_run(db, run_id)
