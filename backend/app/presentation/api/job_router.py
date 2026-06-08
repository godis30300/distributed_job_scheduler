from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.presentation.controllers import job_controller
from app.infrastructure.database.database import get_db
from app.core.security import get_current_user
from app.domain.entities.user import User
from app.presentation.dtos.job_schema import JobCreate, JobResponse, JobUpdate, TriggerResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return job_controller.create_job(db, payload, current_user)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return job_controller.list_jobs(db, current_user=current_user, status=status, keyword=keyword)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return job_controller.get_job_or_404(db, job_id, current_user)


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return job_controller.update_job(db, job_id, payload, current_user)


@router.delete("/{job_id}")
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return job_controller.delete_job(db, job_id, current_user)


@router.patch("/{job_id}/enable", response_model=JobResponse)
def enable_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return job_controller.set_job_enabled(db, job_id, True, current_user)


@router.patch("/{job_id}/disable", response_model=JobResponse)
def disable_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return job_controller.set_job_enabled(db, job_id, False, current_user)


def _trigger_job_response(job_id: str, db: Session, current_user: User) -> TriggerResponse:
    run = job_controller.trigger_job(db, job_id, current_user, trigger_type="manual")
    return TriggerResponse(run_id=run.id, status=run.status)


@router.post("/{job_id}/run", response_model=TriggerResponse)
def run_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _trigger_job_response(job_id, db, current_user)


@router.post("/{job_id}/trigger", response_model=TriggerResponse)
def trigger_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _trigger_job_response(job_id, db, current_user)
