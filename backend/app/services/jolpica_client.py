"""
Jolpica-F1 API client — Ergast-compatible replacement.
Base: https://api.jolpi.ca/ergast/f1
Docs: https://github.com/jolpica/jolpica-f1
Covers 1950-present: schedules, results, standings, qualifying.
"""
import httpx
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class JolpicaClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.jolpica_base_url).rstrip("/")
        self._client = httpx.AsyncClient(timeout=15.0)

    async def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        # Jolpica wants .json suffix
        if not url.endswith(".json"):
            url += ".json"
        try:
            r = await self._client.get(url)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Jolpica {path} error: {e}")
            raise

    async def get_schedule(self, year: int | str = "current") -> Dict[str, Any]:
        return await self._get(f"/{year}")

    async def get_race_results(self, year: int | str = "current", round: int | str = "last") -> Dict[str, Any]:
        return await self._get(f"/{year}/{round}/results")

    async def get_qualifying(self, year: int | str = "current", round: int | str = "last") -> Dict[str, Any]:
        return await self._get(f"/{year}/{round}/qualifying")

    async def get_driver_standings(self, year: int | str = "current") -> Dict[str, Any]:
        return await self._get(f"/{year}/driverStandings")

    async def get_constructor_standings(self, year: int | str = "current") -> Dict[str, Any]:
        return await self._get(f"/{year}/constructorStandings")

    async def get_drivers(self, year: int | str = "current") -> Dict[str, Any]:
        return await self._get(f"/{year}/drivers")

    async def get_constructors(self, year: int | str = "current") -> Dict[str, Any]:
        return await self._get(f"/{year}/constructors")

    async def get_lap_times(self, year: int, round: int, lap: int) -> Dict[str, Any]:
        return await self._get(f"/{year}/{round}/laps/{lap}")

    async def get_pit_stops(self, year: int, round: int) -> Dict[str, Any]:
        return await self._get(f"/{year}/{round}/pitstops")

    async def close(self):
        await self._client.aclose()

jolpica = JolpicaClient()
