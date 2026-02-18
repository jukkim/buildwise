"""BuildWise API - FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, billing, buildings, projects, results, simulations, templates


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
    docs_url="/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return JSON error."""
    return JSONResponse(
        status_code=500,
        content={"type": "internal_error", "title": "Internal Server Error", "status": 500},
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "buildwise-api"}


# API v1 routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(buildings.router, prefix="/api/v1/projects", tags=["buildings"])
app.include_router(templates.router, prefix="/api/v1/buildings/templates", tags=["templates"])
app.include_router(simulations.router, prefix="/api/v1/simulations", tags=["simulations"])
app.include_router(results.router, prefix="/api/v1/simulations", tags=["results"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"])
