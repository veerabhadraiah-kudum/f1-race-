"""
OpenF1 API client — https://api.openf1.org
Docs: https://openf1.org + https://github.com/br-g/openf1
Rate limit: 3 req/s, 30 req/min (free tier). We pace requests via a token bucket.
"""
import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class OpenF1Client:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.openf1_base_url).rstrip("/")
        # pacing: 1 req per 0.4s ≈ 2.5 req/s (under 3 req/s limit)
        self._min_interval = 0.4
        self._last_req = 0.0
        self._client = httpx.AsyncClient(timeout=15.0, headers={"Accept": "application/json"})

    async def _paced_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        import time as _time
        now = _time.monotonic()
        wait = self._min_interval - (now - self._last_req)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_req = _time.monotonic()
        url = f"{self.base_url}{path}"
        try:
            r = await self._client.get(url, params=params)
            if r.status_code == 429:
                # rate limited — backoff
                await asyncio.sleep(1.5)
                r = await self._client.get(url, params=params)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"OpenF1 {path} HTTP {e.response.status_code}: {e}")
            raise
        except Exception as e:
            logger.warning(f"OpenF1 {path} error: {e}")
            raise

    # High-level wrappers mirroring OpenF1 endpoints
    async def get_sessions(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {}
        if year:
            params["year"] = year
        return await self._paced_get("/sessions", params)

    async def get_drivers(self, session_key: int) -> List[Dict[str, Any]]:
        return await self._paced_get("/drivers", {"session_key": session_key})

    async def get_laps(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return await self._paced_get("/laps", params)

    async def get_car_data(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return await self._paced_get("/car_data", params)

    async def get_location(self, session_key: int, driver_number: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"session_key": session_key}
        if driver_number is not None:
            params["driver_number"] = driver_number
        return await self._paced_get("/location", params)

    async def get_intervals(self, session_key: int) -> List[Dict[str, Any]]:
        return await self._paced_get("/intervals", {"session_key": session_key})

    async def get_position(self, session_key: int) -> List[Dict[str, Any]]:
        return await self._paced_get("/position", {"session_key": session_key})

    async def get_stints(self, session_key: int) -> List[Dict[str, Any]]:
        return await self._paced_get("/stints", {"session_key": session_key})

    async def get_weather(self, session_key: int) -> List[Dict[str, Any]]:
        return await self._paced_get("/weather", {"session_key": session_key})

    async def get_race_control(self, session_key: int) -> List[Dict[str, Any]]:
        return await self._paced_get("/race_control", {"session_key": session_key})

    async def get_team_radio(self, session_key: int) -> List[Dict[str, Any]]:
        return await self._paced_get("/team_radio", {"session_key": session_key})

    async def get_pit(self, session_key: int) -> List[Dict[str, Any]]:
        return await self._paced_get("/pit", {"session_key": session_key})

    async def close(self):
        await self._client.aclose()

# Singleton for convenience
openf1 = OpenF1Client()
