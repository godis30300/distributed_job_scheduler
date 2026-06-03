import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
TEST_DB_PATH = BACKEND_ROOT / "test_app.sqlite3"


os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH.as_posix()}")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
