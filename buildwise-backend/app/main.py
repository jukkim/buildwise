"""BuildWise API - FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, billing, buildings, projects, results, simulations, templates

app = FastAPI(
    title="BuildWise API",
    version="0.1.0",
    description="건물 에너지 시뮬레이션 SaaS 플랫폼",
    docs_url="/docs",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
