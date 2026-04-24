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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return job_run_controller.list_job_runs(db, status=status, job_id=job_id)


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
