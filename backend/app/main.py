from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.database import init_db
from app.config.settings import settings

from app.api.routes_projects import (
    router as projects_router,
)

from app.api.routes_risks import (
    router as risks_router,
)

from app.api.routes_simulation import (
    router as simulation_router,
)

from app.api.routes_graph import (
    router as graph_router,
)
from app.api.routes_demo import router as demo_router
from app.api.routes_investigation import router as investigation_router


# ============================================================
# DEADLOCK FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="DEADLOCK API",
    description=(
        "Agentic AI backend for discovering "
        "hidden software-project risks."
    ),
    version="0.1.0",
)


# ============================================================
# CORS
# ============================================================

allowed_origins = [
    origin.strip()
    for origin in settings.frontend_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(
    projects_router
)

app.include_router(
    risks_router
)

app.include_router(
    simulation_router
)

app.include_router(
    graph_router
)

app.include_router(demo_router)
app.include_router(investigation_router)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root() -> dict:
    return {
        "service": "DEADLOCK API",
        "status": "running",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup() -> None:
    init_db()


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "deadlock-backend",
    }
