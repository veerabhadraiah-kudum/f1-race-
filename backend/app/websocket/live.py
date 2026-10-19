"""
WebSocket live feed — streams simulated race state at 10Hz.
Falls back to mock data if no real session is active.
In production, this would bridge Redis pub/sub from live ingest.
"""
import asyncio
import json
import logging
import random
import math
from fastapi import WebSocket, WebSocketDisconnect
from typing import List
from backend.app.services.unified import MOCK_DRIVERS, get_circuit_info

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

def generate_mock_race_state(lap: int, total_laps: int, elapsed: float, speed_boost: float = 1.0):
    """Generate mock car positions for a given lap."""
    cars = []
    random.seed(lap * 100)
    for idx, drv in enumerate(MOCK_DRIVERS):
        # Position jitters with lap
        base_pos = idx + 1 + random.uniform(-0.3, 0.3)
        # Spread field over ~30s
        gap = idx * 1.8 + random.uniform(-0.2, 0.5)
        # Fake X/Y on circuit (ellipse)
        angle = (elapsed * 0.05 + idx * 0.5) % (2*math.pi)
        x = 50 + 40 * math.cos(angle + idx*0.3)
        y = 50 + 30 * math.sin(angle + idx*0.3)
        cars.append({
            "driver_number": drv["driver_number"],
            "abbreviation": drv["abbreviation"],
            "full_name": drv["full_name"],
            "team_name": drv["team_name"],
            "team_colour": drv["team_colour"],
            "position": max(1, min(20, int(round(base_pos)))),
            "gap_to_leader": f"+{gap:.3f}" if idx != 0 else "Leader",
            "interval": f"+{random.uniform(0.2,1.5):.3f}" if idx !=0 else "-",
            "last_lap_time": round(random.uniform(78, 82), 3),
            "compound": random.choice(["SOFT","MEDIUM","HARD"]),
            "tyre_age": random.randint(1, 25),
            "stint": 1,
            "pit_stops": 0 if lap < 20 else random.randint(0,1),
            "speed": round(random.uniform(180, 310), 1),
            "throttle": round(random.uniform(0,100),1),
            "brake": round(random.uniform(0,100),1),
            "gear": random.randint(3,8),
            "drs": random.randint(0,1),
            "rpm": random.randint(8500, 11500),
            "x": round(x,2),
            "y": round(y,2),
            "status": "On Track",
        })
    # Sort by position
    cars.sort(key=lambda c: c["position"])
    return cars

async def live_race_loop(websocket: WebSocket, session_key: str = "mock", total_laps: int = 53, speed: float = 5.0):
    """
    Stream mock race — 10Hz updates, laps advance at speed multiplier.
    speed: wall-clock multiplier (e.g., 5.0 = 5x real time)
    """
    await manager.connect(websocket)
    try:
        lap = 0
        elapsed = 0.0
        circuit = get_circuit_info("monza")
        flag = "GREEN"
        while True:
            lap = min(total_laps, max(1, int(elapsed // 85) + 1))
            if lap >= total_laps:
                flag = "CHEQUERED"
            elif random.random() < 0.002:
                flag = random.choice(["YELLOW","GREEN","SC"])
                if flag == "SC":
                    await asyncio.sleep(0.5)
                    flag = "GREEN"

            cars = generate_mock_race_state(lap, total_laps, elapsed)
            payload = {
                "type": "race_state",
                "session_key": session_key,
                "session_name": f"Mock Race — {circuit.circuit_name}",
                "circuit": circuit.model_dump(),
                "flag": flag,
                "lap": lap,
                "total_laps": total_laps,
                "elapsed_seconds": round(elapsed, 2),
                "cars": cars,
                "race_control_messages": ["GREEN FLAG" if flag=="GREEN" else f"{flag} FLAG"],
                "weather": {"air_temp": 26, "track_temp": 36, "humidity": 55, "rainfall": False},
                "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            }
            await websocket.send_json(payload)
            # 10Hz
            await asyncio.sleep(0.1)
            elapsed += 0.1 * speed * 10  # speed factor
            if flag == "CHEQUERED":
                await asyncio.sleep(2)
                break
    except WebSocketDisconnect:
        logger.info(f"WS disconnect {session_key}")
    except Exception as e:
        logger.warning(f"WS loop error: {e}")
        try:
            await websocket.close()
        except: pass
    finally:
        manager.disconnect(websocket)

async def simulation_progress_ws(websocket: WebSocket):
    """Stream simulation progress (demo)."""
    await websocket.accept()
    try:
        for pct in range(0, 101, 10):
            await websocket.send_json({"type": "progress", "percent": pct, "message": f"Running Monte Carlo... {pct}%"})
            await asyncio.sleep(0.15)
        await websocket.send_json({"type": "done", "message": "Simulation complete — fetch via POST /api/simulate"})
    except WebSocketDisconnect:
        pass
