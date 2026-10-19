from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import time
import logging
from backend.app.core.schemas import SimulationRequest, SimulationResponse
from backend.app.services.unified import get_circuit_info, fetch_session_bundle, MOCK_SESSION, CIRCUIT_CALIBRATION
from backend.app.simulation.monte_carlo import Strategy, compare_strategies, preset_strategies
from backend.app.simulation.strategy import optimize_pit_windows, full_strategy_optimization

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "service": "f1-race-advanced-simulation", "version": "1.0.0", "data_sources": ["jolpica","openf1","fastf1"]}

@router.get("/circuits")
async def list_circuits():
    return {
        "circuits": [
            {"key": k, "laps": v["laps"], "lap_length_km": v["lap_length_km"], "pit_loss": v["pit_loss_seconds"], "sc_prob": v["sc_probability_per_lap"]}
            for k, v in CIRCUIT_CALIBRATION.items()
        ],
        "count": len(CIRCUIT_CALIBRATION)
    }

@router.get("/circuits/{circuit_key}")
async def get_circuit(circuit_key: str):
    try:
        info = get_circuit_info(circuit_key)
        return info.model_dump()
    except Exception as e:
        raise HTTPException(404, str(e))

@router.get("/sessions")
async def get_sessions(year: int = Query(..., ge=1950, le=2030)):
    try:
        bundle = await fetch_session_bundle(year)
        return bundle
    except Exception as e:
        logger.warning(f"sessions {year} error: {e}")
        # Return mock fallback + error
        return {"year": year, "mock": MOCK_SESSION, "error": str(e), "note": "Returning mock data due to upstream error"}

@router.get("/session/{year}/{round_num}")
async def get_session_detail(year: int, round_num: int):
    try:
        bundle = await fetch_session_bundle(year, round_num)
        return bundle
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch session {year} R{round_num}: {e}")

@router.post("/simulate", response_model=SimulationResponse)
async def run_simulation(req: SimulationRequest):
    """
    Run Monte Carlo race simulation.
    If strategies not provided, uses presets for the circuit.
    """
    t0 = time.perf_counter()
    try:
        circuit = get_circuit_info(req.circuit_key)
        total_laps = req.total_laps or circuit.laps or 55

        # Build strategies
        strategies = []
        if req.strategies:
            for idx, s in enumerate(req.strategies):
                strategies.append(Strategy(
                    id=s.get("id", f"S{idx}"),
                    compounds=s.get("compounds", ["MEDIUM","HARD"]),
                    pit_laps=s.get("pit_laps", [total_laps//2]),
                    base_pace=s.get("base_pace", None)
                ))
        else:
            strategies = preset_strategies(total_laps, req.circuit_key)

        # Resolve circuit calibration
        pit_loss = circuit.pit_loss_seconds
        sc_prob = circuit.sc_probability_per_lap
        mult = circuit.degradation_multiplier

        results, best_id = compare_strategies(
            strategies=strategies,
            total_laps=total_laps,
            base_pace=req.base_lap_time,
            track_temp_c=req.track_temp_c,
            circuit_multiplier=mult,
            pit_loss_mean=pit_loss,
            sc_prob_per_lap=sc_prob,
            n_simulations=req.n_simulations,
            seed=req.seed or 42,
            include_safety_car=req.include_safety_car,
        )

        compute_ms = int((time.perf_counter() - t0) * 1000)

        # Convert to SimulationResult schema
        from backend.app.core.schemas import SimulationResult
        sim_results = []
        for r in results:
            sim_results.append(SimulationResult(
                strategy_id=r["strategy_id"],
                compounds=r["compounds"],
                pit_laps=r["pit_laps"],
                mean_total_time=r["mean_total_time"],
                median_total_time=r["median_total_time"],
                std_total_time=r["std_total_time"],
                p5_total_time=r["p5_total_time"],
                p95_total_time=r["p95_total_time"],
                fastest_time=r["fastest_time"],
                slowest_time=r["slowest_time"],
                win_probability=r["win_probability"],
                podium_probability=r["podium_probability"],
                points_probability=r["points_probability"],
                samples=r.get("samples"),
            ))

        return SimulationResponse(
            request=req,
            results=sim_results,
            best_strategy_id=best_id,
            compute_ms=compute_ms,
            meta={
                "circuit": circuit.model_dump(),
                "total_laps": total_laps,
                "pit_loss": pit_loss,
                "sc_prob": sc_prob,
                "circuit_multiplier": mult,
            }
        )
    except Exception as e:
        logger.exception("Simulation failed")
        raise HTTPException(500, f"Simulation failed: {e}")

@router.post("/strategy/optimize")
async def optimize_strategy(
    circuit_key: str = "monza",
    total_laps: int = 53,
    base_lap_time: float = 85.0,
    n_simulations: int = 3000,
):
    """
    Full strategy optimization — evaluates all compound sequences at optimal pit windows.
    """
    t0 = time.perf_counter()
    try:
        circuit = get_circuit_info(circuit_key)
        total_laps = total_laps or circuit.laps or 53
        pit_loss = circuit.pit_loss_seconds
        sc_prob = circuit.sc_probability_per_lap

        results = full_strategy_optimization(
            total_laps=total_laps,
            base_pace=base_lap_time,
            pit_loss_mean=pit_loss,
            sc_prob_per_lap=sc_prob,
            n_simulations=n_simulations,
        )
        compute_ms = int((time.perf_counter() - t0) * 1000)
        return {"circuit": circuit.model_dump(), "results": results, "compute_ms": compute_ms, "total_laps": total_laps}
    except Exception as e:
        logger.exception("Optimize failed")
        raise HTTPException(500, str(e))

@router.get("/telemetry/mock/{driver}")
async def mock_telemetry(driver: str):
    """
    Mock telemetry for frontend demo — returns synthetic speed/gear trace.
    Replace with real FastF1 data when available.
    """
    import math, random
    random.seed(hash(driver) % 10000)
    points = []
    for i in range(200):
        dist = i / 200  # 0..1 lap
        # Simulate speed: fast on straights, slow in corners
        speed = 280 - 80*abs(math.sin(dist*math.pi*6)) - random.uniform(-5,5)
        speed = max(60, min(340, speed))
        points.append({
            "distance": round(dist, 4),
            "speed": round(speed, 1),
            "throttle": round(80 + 20*math.sin(dist*math.pi*4) + random.uniform(-5,5), 1),
            "brake": round(max(0, 100 - 80*math.sin(dist*math.pi*4)), 1),
            "gear": max(1, min(8, int(3 + 4*math.sin(dist*math.pi*3) + random.uniform(-0.5,0.5)))),
            "drs": 1 if dist > 0.3 and dist < 0.5 else 0,
            "rpm": int(9000 + 2000*math.sin(dist*math.pi*5)),
        })
    return {"driver": driver, "points": points, "note": "Mock data — connect FastF1 for real telemetry"}
