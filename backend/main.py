"""
main.py
───────
Application entry-point.

Bootstraps the FastAPI app, mounts Socket.io, wires up all route modules,
initialises the SQLite database on startup, and serves the compiled React
frontend as static files in production.

Run locally:
    uvicorn backend.main:socket_app --reload --port 8000
"""

import socketio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database.db import init_db

# ── Socket.io setup ────────────────────────────────────────────────────────────
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.CORS_ORIGINS,
    logger=False,
    engineio_logger=False,
)


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    print(f"[App] {settings.APP_NAME} v{settings.APP_VERSION} ready.")
    yield
    # Shutdown (add cleanup here if needed)
    print("[App] Shutting down.")


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route registration ─────────────────────────────────────────────────────────
from backend.routes import cases, evidence, analysis

app.include_router(cases.router,    prefix="/api/cases",    tags=["Cases"])
app.include_router(evidence.router, prefix="/api/evidence", tags=["Evidence"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])

# Direct media endpoint alias for frontend convenience
@app.get("/api/media/{evidence_id}", tags=["Media"])
async def direct_media_stream(evidence_id: str):
    return await evidence.stream_media(evidence_id)



# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Quick liveness probe."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ── Socket.io events ──────────────────────────────────────────────────────────
@sio.event
async def connect(sid, environ):
    print(f"[Socket.io] Client connected: {sid}")
    await sio.emit("server:connected", {"message": "ForenSight AI connected."}, to=sid)


@sio.event
async def disconnect(sid):
    print(f"[Socket.io] Client disconnected: {sid}")


# ── Mount Socket.io as ASGI sub-application ───────────────────────────────────
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ── Serve compiled React frontend in production ────────────────────────────────
# Uncomment after running `npm run build` in /frontend:
# from fastapi.staticfiles import StaticFiles
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
