"""
Core physics model — combines tyre, fuel, track, weather into lap time.

lap_time = base_pace_d + offset_c + wear_{c} * age * (1 + phi * fuel_remaining) + q * age^2
           - fuel_burn * lap + temp_effect + noise

This mirrors RuchirBhatia4/Pitwall-AI:
  t = base_d + offset_c + wear_{c,team}·a·(1+φ·fuel_remaining(n)) + q·a² − fuel_burn·n + ε
"""
from dataclasses import dataclass
from typing import Optional
from backend.app.simulation.tyre import get_tyre_params, tyre_degradation_seconds
from backend.app.simulation.fuel import FuelModel

@dataclass
class PhysicsConfig:
    base_pace: float = 85.0  # driver/car base (seconds) — zero-fuel, new mediums
    fuel_model: Optional[FuelModel] = None
    track_temp_c: float = 35.0
    air_temp_c: float = 25.0
    circuit_multiplier: float = 1.0
    # Aero / DRS
    drs_gain: float = 0.25  # s per lap when DRS available
    # Track evolution
    track_evolution_per_lap: float = -0.005  # track rubbers in, up to -0.3s over race
    # Cold tyre penalty (outlap)
    cold_tyre_penalty: float = 1.2  # s on first lap after pit

def compute_lap_time(
    lap: int,
    tyre_age: int,
    compound: str,
    config: PhysicsConfig,
    is_outlap: bool = False,
    has_drs: bool = False,
    noise: float = 0.0,
) -> float:
    """Compute single lap time in seconds."""
    # Tyre degradation
    tyre_params = get_tyre_params(compound, config.track_temp_c, config.circuit_multiplier)
    deg = tyre_degradation_seconds(tyre_age, tyre_params)

    # Fuel correction
    fuel_penalty = 0.0
    if config.fuel_model:
        fuel_penalty = config.fuel_model.fuel_remaining(lap) * config.fuel_model.weight_effect_s_per_kg

    # Track evolution (negative = faster)
    evolution = config.track_evolution_per_lap * lap
    evolution = max(evolution, -0.4)  # cap

    # DRS
    drs = -config.drs_gain if has_drs else 0.0

    # Cold tyre
    cold = config.cold_tyre_penalty if is_outlap and tyre_age == 1 else 0.0

    total = config.base_pace + deg + fuel_penalty + evolution + drs + cold + noise
    return max(40.0, total)  # sanity floor

def compute_stint_times(
    start_lap: int,
    stint_length: int,
    compound: str,
    config: PhysicsConfig,
    has_drs: bool = False,
    noise_array: Optional[list] = None,
) -> list[float]:
    """Compute stint lap times."""
    times = []
    for i in range(stint_length):
        lap = start_lap + i
        age = i + 1
        is_out = (i == 0 and start_lap != 1)  # outlap if not race start
        n = noise_array[i] if noise_array and i < len(noise_array) else 0.0
        times.append(compute_lap_time(lap, age, compound, config, is_outlap=is_out, has_drs=has_drs, noise=n))
    return times
