from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

router = APIRouter(tags=["metrics"])

api_requests_total = Counter("scheduler_api_requests_total", "Total API requests")
worker_load = Gauge("scheduler_worker_load", "Worker load hint")
queue_length = Gauge("scheduler_queue_length", "Queue length hint")


@router.get("/metrics")
def metrics():
    api_requests_total.inc()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
