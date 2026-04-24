from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.controllers.dashboard_controller import dashboard_summary
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.system_schema import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return dashboard_summary(db)
