from fastapi import APIRouter, Response
from app.core.metrics import metrics

router = APIRouter(tags=["Observability"])


@router.get("/metrics", response_class=Response)
def get_prometheus_metrics():
    """
    Exposes application and recovery pipeline metrics in standard Prometheus text format (2.0).
    Scraped by Prometheus, Grafana Agent, or Datadog.
    """
    body = metrics.generate_prometheus_text()
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
