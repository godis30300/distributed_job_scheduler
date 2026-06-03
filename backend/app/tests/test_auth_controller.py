import uuid

import pytest
from fastapi import HTTPException

from app.controllers.auth_controller import change_password, login_user, register_user
from app.core.database import SessionLocal, init_db
from app.core.security import verify_password
from app.models.user import User
from app.schemas.auth_schema import ChangePasswordRequest, LoginRequest, RegisterRequest


def setup_module(module) -> None:
    init_db()


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def unique_identity(prefix: str) -> tuple[str, str]:
    suffix = uuid.uuid4().hex
    return f"{prefix}_{suffix}", f"{prefix}_{suffix}@example.com"


def test_register_user_hashes_password(db_session) -> None:
    username, email = unique_identity("auth_register")

    user = register_user(
        db_session,
        RegisterRequest(username=username, email=email, password="StrongPass123!", role="operator"),
    )

    assert user.username == username
    assert user.email == email
    assert user.password_hash != "StrongPass123!"
    assert verify_password("StrongPass123!", user.password_hash)


def test_register_user_rejects_duplicate_username_and_email(db_session) -> None:
    username, email = unique_identity("auth_duplicate")
    register_user(
        db_session,
        RegisterRequest(username=username, email=email, password="StrongPass123!", role="operator"),
    )

    with pytest.raises(HTTPException, match="Username already exists"):
        register_user(
            db_session,
            RegisterRequest(username=username, email=f"other-{email}", password="StrongPass123!", role="operator"),
        )

    with pytest.raises(HTTPException, match="Email already exists"):
        register_user(
            db_session,
            RegisterRequest(username=f"other_{username}", email=email, password="StrongPass123!", role="operator"),
        )


def test_login_user_returns_token_for_valid_credentials(db_session) -> None:
    username, email = unique_identity("auth_login")
    register_user(
        db_session,
        RegisterRequest(username=username, email=email, password="StrongPass123!", role="admin"),
    )

    token_response = login_user(db_session, LoginRequest(username=username, password="StrongPass123!"))

    assert token_response.access_token
    assert token_response.user.username == username
    assert token_response.user.role == "admin"


def test_login_user_rejects_invalid_password(db_session) -> None:
    username, email = unique_identity("auth_invalid_login")
    register_user(
        db_session,
        RegisterRequest(username=username, email=email, password="StrongPass123!", role="operator"),
    )

    with pytest.raises(HTTPException, match="Invalid username or password"):
        login_user(db_session, LoginRequest(username=username, password="wrong-password"))


def test_change_password_replaces_existing_hash(db_session) -> None:
    username, email = unique_identity("auth_change_password")
    current_user = register_user(
        db_session,
        RegisterRequest(username=username, email=email, password="StrongPass123!", role="operator"),
    )
    old_hash = current_user.password_hash

    result = change_password(
        db_session,
        current_user,
        ChangePasswordRequest(old_password="StrongPass123!", new_password="StrongerPass456!"),
    )
    db_session.refresh(current_user)

    assert result == {"message": "password updated"}
    assert current_user.password_hash != old_hash
    assert verify_password("StrongerPass456!", current_user.password_hash)
    assert not verify_password("StrongPass123!", current_user.password_hash)


def test_change_password_rejects_wrong_old_password(db_session) -> None:
    username, email = unique_identity("auth_wrong_old_password")
    current_user = register_user(
        db_session,
        RegisterRequest(username=username, email=email, password="StrongPass123!", role="operator"),
    )

    with pytest.raises(HTTPException, match="Old password is incorrect"):
        change_password(
            db_session,
            current_user,
            ChangePasswordRequest(old_password="bad-old-password", new_password="StrongerPass456!"),
        )

    reloaded_user = db_session.query(User).filter(User.id == current_user.id).first()
    assert reloaded_user is not None
    assert verify_password("StrongPass123!", reloaded_user.password_hash)
