import pytest
from app.infrastructure.database.database import SessionLocal, init_db, engine, Base
from sqlalchemy.orm import Session

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()
    yield

@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
