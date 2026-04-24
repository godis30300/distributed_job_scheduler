from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.controllers import auth_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth_schema import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return auth_controller.register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_controller.login_user(db, payload)


@router.post("/logout")
def logout():
    return {"message": "logout success. client should remove token"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return auth_controller.change_password(db, current_user, payload)
