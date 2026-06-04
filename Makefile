.PHONY: test test-unit test-integration

test: test-unit test-integration

test-unit:
	cd backend && DATABASE_URL=sqlite:///./test.db JWT_SECRET_KEY=unit-test-secret PYTHONPATH=. python3 -m pytest tests/unit/

test-integration:
	cd backend && DATABASE_URL=postgresql+psycopg2://postgres:change-me-postgres-password@localhost:5432/jobscheduler JWT_SECRET_KEY=change-me-jwt-secret PYTHONPATH=. python3 -m pytest tests/integration/
