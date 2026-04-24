from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.routers import (
    auth_router,
    dashboard_router,
    job_router,
    job_run_router,
    metrics_router,
    scheduler_router,
    system_router,
    worker_router,
)

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {"service": settings.app_name, "docs": "/docs"}


app.include_router(auth_router.router, prefix=settings.api_prefix)
app.include_router(job_router.router, prefix=settings.api_prefix)
app.include_router(job_run_router.router, prefix=settings.api_prefix)
app.include_router(scheduler_router.router, prefix=settings.api_prefix)
app.include_router(worker_router.router, prefix=settings.api_prefix)
app.include_router(dashboard_router.router, prefix=settings.api_prefix)
app.include_router(system_router.router, prefix=settings.api_prefix)
app.include_router(metrics_router.router, prefix=settings.api_prefix)
