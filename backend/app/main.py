from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.database import init_db
from app.api.routes_projects import router as projects_router
from app.api.routes_risks import router as risks_router
from app.api.routes_simulation import router as simulation_router
from app.api.routes_graph import router as graph_router


app = FastAPI(
    title="DEADLOCK API",
    description="Agentic AI backend for discovering hidden software-project risks.",
    version="0.1.0",
)

# Allow the Laptop 2 frontend to communicate with this backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this later for production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes.
app.include_router(projects_router)
app.include_router(risks_router)
app.include_router(simulation_router)
app.include_router(graph_router)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "deadlock-backend"
    }