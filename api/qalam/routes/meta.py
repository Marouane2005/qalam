import json

from fastapi import APIRouter, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

router = APIRouter()


@router.get("/health", tags=["meta"])
def health(request: Request) -> Response:
    database = "down"
    redis_status = "down"
    try:
        session = request.app.state.session_factory()
        try:
            session.execute(text("SELECT 1"))
            database = "ok"
        finally:
            session.close()
    except Exception:
        database = "down"
    try:
        if request.app.state.redis.ping():
            redis_status = "ok"
    except Exception:
        redis_status = "down"
    if database == "ok" and redis_status == "ok":
        status = "ok"
        code = 200
    elif database == "ok":
        status = "degraded"
        code = 200
    else:
        status = "down"
        code = 503
    payload = {"status": status, "database": database, "redis": redis_status}
    return Response(content=json.dumps(payload), media_type="application/json", status_code=code)


@router.get("/metrics", tags=["meta"])
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
