from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.presentation.controllers import scheduler_controller
from app.infrastructure.database.database import get_db
from app.core.security import get_current_user
from app.domain.entities.user import User

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.post("/scan")
def scan_due_jobs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return scheduler_controller.scan_due_jobs(db)


@router.get("/status")
def status(_: User = Depends(get_current_user)):
    return scheduler_controller.scheduler_status()


@router.get("/leader")
def leader(_: User = Depends(get_current_user)):
    return {"leader": "db-lock-active", "strategy": "SELECT FOR UPDATE SKIP LOCKED"}
