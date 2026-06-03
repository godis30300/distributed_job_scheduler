from sqlalchemy import text
from sqlalchemy.orm import Session


def health_check(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database = "connected"
        status = "healthy"
    except Exception:
        database = "disconnected"
        status = "unhealthy"

    return {
        "status": status,
        "database": database,
        "api": "running",
        "worker_hint": "check worker deployment or /api/dashboard/summary",
    }


def system_nodes() -> list[dict]:
    # Placeholder for Kubernetes integration.
    # Later can call Kubernetes Python client.
    return [
        {"name": "proxmox-vm-1", "role": "control-plane", "status": "Ready"},
        {"name": "proxmox-vm-2", "role": "control-plane", "status": "Ready"},
        {"name": "proxmox-vm-3", "role": "control-plane", "status": "Ready"},
    ]


def system_pods() -> list[dict]:
    return [
        {"name": "api", "status": "Running"},
        {"name": "scheduler", "status": "Running"},
        {"name": "worker", "status": "Running"},
        {"name": "postgresql", "status": "Running"},
    ]
