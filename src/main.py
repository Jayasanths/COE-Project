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

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients.router, prefix="/api/clients", tags=["clients"])
app.include_router(consent.router, prefix="/api/consent", tags=["consent"])
app.include_router(briefs.router, prefix="/api/briefs", tags=["briefs"])
app.include_router(actions.router, prefix="/api/actions", tags=["actions"])


@app.get("/health")
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


from fastapi import HTTPException

DIST_DIR = Path(__file__).resolve().parent.parent / "ui" / "dist"

if DIST_DIR.exists():
    if (DIST_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/")
    async def serve_root():
        return FileResponse(DIST_DIR / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api") or full_path in ("docs", "openapi.json", "health"):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DIST_DIR / "index.html")
