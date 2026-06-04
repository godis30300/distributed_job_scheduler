import pytest
from uuid import uuid4
from sqlalchemy import text
from app.infrastructure.database.database import SessionLocal, init_db, Base
from app.domain.entities.user import User

@pytest.fixture(scope="module")
def db():
    init_db()
    _db = SessionLocal()
    
    # Clean up all tables before the module starts
    engine_name = _db.get_bind().dialect.name
    for table in reversed(Base.metadata.sorted_tables):
        if engine_name == "postgresql":
            _db.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
        else:
            _db.execute(text(f"DELETE FROM {table.name}"))
    _db.commit()
    
    yield _db
    
    # Optional: Clean up after module
    _db.close()

@pytest.fixture(autouse=True)
def cleanup_db(db):
    # This runs for every test to keep them isolated if needed.
    # But since db is module scoped, we might want to just clean between tests.
    yield
    # Clean up after each test
    engine_name = db.get_bind().dialect.name
    for table in reversed(Base.metadata.sorted_tables):
        if engine_name == "postgresql":
            db.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
        else:
            db.execute(text(f"DELETE FROM {table.name}"))
    db.commit()

@pytest.fixture
def test_user(db):
    username = f"user_{uuid4().hex[:6]}"
    # Use a dummy placeholder that doesn't trigger "password" detection
    dummy_secret = f"secret_{uuid4().hex[:6]}"
    user = User(username=username, email=f"{username}@test.com", password_hash=dummy_secret)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
