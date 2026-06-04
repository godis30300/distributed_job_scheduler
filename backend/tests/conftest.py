import pytest
from app.infrastructure.database.database import SessionLocal, init_db, engine, Base
from sqlalchemy.orm import Session

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    init_db()
    yield

@pytest.fixture(autouse=True)
def clean_db(db: Session):
    # This runs before every test
    from app.domain.entities.job_log import JobLog
    from app.domain.entities.job_run import JobRun
    from app.domain.entities.job import Job
    from app.domain.entities.user import User
    from sqlalchemy import text
    
    db.query(JobLog).delete()
    db.query(JobRun).delete()
    db.query(Job).delete()
    # Keep users for now as some tests use module-scoped auth
    db.commit()
    yield

@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
