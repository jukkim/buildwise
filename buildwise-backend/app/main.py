"""BuildWise API - FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import ai, auth, billing, buildings, projects, results, simulations, templates
from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown: dispose DB engine
    from app.db import engine

    await engine.dispose()


app = FastAPI(
    title="BuildWise API",
    version="0.1.0",
    description="Building Energy Simulation SaaS Platform",
    docs_url="/docs" if settings.debug else None,
    openapi_url="/api/v1/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)


# Security response headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# CORS configuration: restrict methods/headers, load origins from settings
_cors_origins = (
    settings.cors_origins.split(",")
    if hasattr(settings, "cors_origins") and settings.cors_origins
    else ["http://localhost:5173", "http://localhost:3000"]
)

# Production guard: reject wildcard origins in non-debug mode
if not settings.debug and "*" in _cors_origins:
    raise ValueError("Wildcard CORS origins are not allowed in production (debug=False)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-Id"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return JSON error."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"type": "internal_error", "title": "Internal Server Error", "status": 500},
    )


@app.get("/health")
async def health_check() -> dict:
    resp: dict = {"status": "ok", "service": "buildwise-api"}
    if settings.debug:
        resp["version"] = app.version
    return resp


# API v1 routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(buildings.router, prefix="/api/v1/projects", tags=["buildings"])
app.include_router(templates.router, prefix="/api/v1/buildings/templates", tags=["templates"])
app.include_router(simulations.router, prefix="/api/v1/simulations", tags=["simulations"])
app.include_router(results.router, prefix="/api/v1/simulations", tags=["results"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["ai"])
