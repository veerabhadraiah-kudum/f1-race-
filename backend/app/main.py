from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
from pathlib import Path
from backend.app.core.config import settings
from backend.app.api.routes import router as api_router
from backend.app.websocket.live import live_race_loop, simulation_progress_ws

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="F1 Advanced Race Simulation",
    description="Real-time F1 race simulation with physics-accurate tyre/fuel models, Monte Carlo strategy engine, and live telemetry ingestion (FastF1 + OpenF1 + Jolpica)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow frontend (Vite default 5173) and any preview host
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
origins += ["*"]  # allow preview in dev; tighten in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api", tags=["api"])

@app.get("/")
async def root():
    return {
        "service": "F1 Advanced Race Simulation",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "simulate": "POST /api/simulate",
        "optimize": "POST /api/strategy/optimize",
        "ws_live": "WS /ws/live/{session_key}",
        "frontend": "http://localhost:5173 (run frontend)",
        "data_sources": {
            "jolpica": "https://api.jolpi.ca/ergast/f1",
            "openf1": "https://api.openf1.org/v1",
            "fastf1": "Python package (cached)",
            "fia_doc": "FIA PDFs via fia-doc",
        }
    }

@app.websocket("/ws/live/{session_key}")
async def ws_live(websocket: WebSocket, session_key: str):
    await live_race_loop(websocket, session_key)

@app.websocket("/ws/live")
async def ws_live_default(websocket: WebSocket):
    await live_race_loop(websocket, "mock")

@app.websocket("/ws/simulation")
async def ws_simulation(websocket: WebSocket):
    await simulation_progress_ws(websocket)

# Serve frontend static if built
static_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
if static_dir.exists():
    app.mount("/app", StaticFiles(directory=str(static_dir), html=True), name="frontend")

@app.on_event("startup")
async def startup():
    logger.info(f"F1 Simulation API starting — ENV={settings.env} CORS={origins}")
    Path(settings.fastf1_cache_dir).mkdir(parents=True, exist_ok=True)

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down...")
    try:
        from backend.app.services.openf1_client import openf1
        await openf1.close()
        from backend.app.services.jolpica_client import jolpica
        await jolpica.close()
    except: pass
