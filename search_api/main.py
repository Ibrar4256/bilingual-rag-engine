"""
Search API — FastAPI app entrypoint.

Run locally: uvicorn search_api.main:app --reload --port 8000
"""

import os
import time
import uuid
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from search_api.routers import admin_config, agent, auth, category, chunking, companies, conversations, evaluation, health, logs, observability, rag
from search_api.services.log_buffer import log_sink

app = FastAPI(
    title="Bilingual Search API",
    version="1.0.0",
    description="Hybrid (BM25 + vector, RRF-fused) bilingual search over Hungarian/English category and company data.",
    docs_url="/docs",
    redoc_url="/redoc",
)

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
)


# ---------------------------------------------------------------------------
# Middleware: request ID + response timing
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:12]
    request.state.request_id = request_id
    start = time.perf_counter()

    response: Response = await call_next(request)

    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"

    return response


# ---------------------------------------------------------------------------
# Middleware: simple in-memory rate limiting (per-IP, sliding window)
# ---------------------------------------------------------------------------
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "60"))
_request_log: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_EXEMPT = {"/health", "/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if RATE_LIMIT_RPM <= 0 or request.url.path in RATE_LIMIT_EXEMPT:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - 60

    if len(_request_log) > 10_000:
        stale = [ip for ip, ts in _request_log.items() if not ts or ts[-1] < window_start]
        for ip in stale:
            del _request_log[ip]

    timestamps = _request_log[client_ip]
    _request_log[client_ip] = [t for t in timestamps if t > window_start]

    if len(_request_log[client_ip]) >= RATE_LIMIT_RPM:
        retry_after = int(60 - (now - _request_log[client_ip][0])) + 1
        logger.warning(f"Rate limit exceeded: ip={client_ip} rpm={RATE_LIMIT_RPM}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again shortly."},
            headers={"Retry-After": str(retry_after)},
        )

    _request_log[client_ip].append(now)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Unhandled error [{request_id}]: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )


logger.add(log_sink, level="DEBUG", format="{message}")

auth.seed_admin_user()

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin_config.router)
app.include_router(admin_config.etl_router)
app.include_router(category.router)
app.include_router(companies.router)
app.include_router(rag.router)
app.include_router(evaluation.router)
app.include_router(observability.router)
app.include_router(chunking.router)
app.include_router(agent.router)
app.include_router(conversations.router)
app.include_router(logs.router)
