import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import create_tables, AsyncSessionLocal

from app.api import auth, surveys, analytics, nlp, forecast

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("surveyiq")

app = FastAPI(
    title="SurveyIQ API",
    description="AI-Powered Survey & Feedback Intelligence Platform",
    version="1.0.0",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start_time = time.perf_counter()

    response = await call_next(request)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": elapsed_ms,
            "request_id": request_id,
        },
    )

    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    response.headers["content-security-policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    return response

@app.on_event("startup")
async def on_startup():
    await create_tables()

app.include_router(auth.router)
app.include_router(surveys.router)
app.include_router(analytics.router)
app.include_router(nlp.router)
app.include_router(forecast.router)

@app.get("/")
async def root():
    return {"message": "Welcome to SurveyIQ API", "environment": settings.APP_ENV}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "surveyiq-api",
        "environment": settings.APP_ENV,
    }

@app.get("/ready")
async def readiness():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        logger.exception("Database readiness check failed")
        return {"status": "degraded", "database": "unavailable", "error": str(exc)}
