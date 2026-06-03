from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.domain.entities.user import User
from app.infrastructure.repositories.user_repository import UserRepository
from app.presentation.dtos.auth_schema import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse, UserResponse


def register_user(db: Session, payload: RegisterRequest) -> User:
    repo = UserRepository(db)
    if repo.find_by_username(payload.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    if payload.email and repo.find_by_email(payload.email):
        raise HTTPException(status_code=409, detail="Email already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    repo.add(user)
    repo.commit()
    repo.refresh(user)
    return user


def login_user(db: Session, payload: LoginRequest) -> TokenResponse:
    repo = UserRepository(db)
    user = repo.find_by_username(payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(subject=user.username)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


def change_password(db: Session, current_user: User, payload: ChangePasswordRequest) -> dict:
    repo = UserRepository(db)
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    current_user.password_hash = hash_password(payload.new_password)
    repo.commit()
    return {"message": "password updated"}
