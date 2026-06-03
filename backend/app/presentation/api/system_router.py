from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.presentation.controllers.system_controller import health_check, system_nodes, system_pods
from app.infrastructure.database.database import get_db
from app.core.security import get_current_user
from app.domain.entities.user import User
from app.presentation.dtos.system_schema import HealthResponse

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    return health_check(db)


@router.get("/nodes")
def nodes(_: User = Depends(get_current_user)):
    return system_nodes()


@router.get("/pods")
def pods(_: User = Depends(get_current_user)):
    return system_pods()


@router.get("/version")
def version():
    return {"version": "0.1.0", "service": "distributed-job-scheduler"}
