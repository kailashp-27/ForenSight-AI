"""
main.py
───────
Application entry-point.

Bootstraps the FastAPI app, mounts Socket.io, wires up all route modules,
and serves the compiled React frontend as static files (production).

Run locally:
    uvicorn backend.main:app --reload --port 8000
"""

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings

# ── Socket.io setup ────────────────────────────────────────────────────────────
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.CORS_ORIGINS,
)

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route registration (modules will be added as phases progress) ──────────────
# from backend.routes import cases, evidence, analysis, chat
# app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
# app.include_router(evidence.router, prefix="/api/evidence", tags=["Evidence"])
# app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
# app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Quick liveness probe."""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


# ── Socket.io event stubs ──────────────────────────────────────────────────────
@sio.event
async def connect(sid, environ):
    print(f"[Socket.io] Client connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[Socket.io] Client disconnected: {sid}")


# ── Mount Socket.io as ASGI sub-application ───────────────────────────────────
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ── Serve compiled React frontend in production ────────────────────────────────
# Uncomment after running `npm run build` in /frontend:
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
