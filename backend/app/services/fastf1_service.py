"""
FastF1 service — Python wrapper for official F1 timing + telemetry.
Docs: https://docs.fastf1.dev
Requires: pip install fastf1
We enable caching to ./data/cache and provide sync helpers wrapped for async usage.
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import fastf1
    import pandas as pd
    FASTF1_AVAILABLE = True
    # Enable cache
    cache_path = Path(settings.fastf1_cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_path))
    logger.info(f"FastF1 cache enabled at {cache_path}")
except ImportError:
    FASTF1_AVAILABLE = False
    logger.warning("FastF1 not installed — telemetry features disabled. pip install fastf1")

def get_session(year: int, gp: str | int, session: str):
    """Load a FastF1 session. gp can be round number or GP name (e.g., 'Monaco Grand Prix')."""
    if not FASTF1_AVAILABLE:
        raise RuntimeError("FastF1 not installed")
    s = fastf1.get_session(year, gp, session)
    s.load(telemetry=True, weather=True, messages=True)
    return s

def get_event_schedule(year: int):
    if not FASTF1_AVAILABLE:
        raise RuntimeError("FastF1 not installed")
    return fastf1.get_event_schedule(year)

def get_telemetry_for_driver(session, driver: str):
    """Return telemetry DataFrame for a driver abbreviation (e.g., 'VER')."""
    drv = session.laps.pick_driver(driver)
    if drv.empty:
        return None
    # Fastest lap telemetry
    try:
        tel = drv.pick_fastest().get_telemetry()
        return tel
    except Exception as e:
        logger.warning(f"Telemetry for {driver}: {e}")
        return None

def list_drivers(session) -> List[str]:
    return list(session.drivers) if hasattr(session, 'drivers') else []

def session_to_summary(session) -> Dict[str, Any]:
    """Convert loaded FastF1 session to JSON-serializable summary."""
    try:
        event = session.event
        return {
            "year": int(event["EventDate"].year) if hasattr(event["EventDate"], "year") else None,
            "event_name": event["EventName"] if "EventName" in event else str(event.get("EventName","")),
            "event_format": event.get("EventFormat","") if hasattr(event, "get") else "",
            "round": int(event["RoundNumber"]) if "RoundNumber" in event else None,
            "circuit": event.get("Location","") if hasattr(event, "get") else "",
            "session_name": session.name,
            "session_date": str(session.date) if session.date else None,
            "drivers": list(session.results.index) if hasattr(session, "results") and session.results is not None else [],
        }
    except Exception as e:
        logger.warning(f"session_to_summary error: {e}")
        return {"session_name": getattr(session, "name", "Unknown")}

# Async wrappers for FastAPI (run in threadpool)
import asyncio
from concurrent.futures import ThreadPoolExecutor
_executor = ThreadPoolExecutor(max_workers=2)

async def async_get_session(year: int, gp: str | int, session: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, get_session, year, gp, session)

async def async_get_schedule(year: int):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, get_event_schedule, year)
