from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.database import init_db
from app.api.routes_projects import router as projects_router
from app.api.routes_risks import router as risks_router
from app.api.routes_simulation import router as simulation_router


# ============================================================
# DEADLOCK FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="DEADLOCK API",
    description="Agentic AI backend for discovering hidden software-project risks.",
    version="0.1.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(projects_router)
app.include_router(risks_router)
app.include_router(simulation_router)


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