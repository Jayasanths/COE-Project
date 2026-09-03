"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import actions, briefs, clients, consent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load synthetic clients once at startup.

    Uses the lifespan protocol rather than the deprecated router-level
    @on_event("startup") hook, which FastAPI does not reliably fire for
    included routers.
    """
    briefs.load_clients()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Psych Discharge Handover API",
    description="Consent-aware continuity summary for psychiatric discharge handovers.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients.router, prefix="/api/clients", tags=["clients"])
app.include_router(consent.router, prefix="/api/consent", tags=["consent"])
app.include_router(briefs.router, prefix="/api/briefs", tags=["briefs"])
app.include_router(actions.router, prefix="/api/actions", tags=["actions"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
