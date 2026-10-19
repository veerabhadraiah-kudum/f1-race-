from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# Unified schemas — all ingest feeds fold into these

Compound = Literal["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET", "UNKNOWN"]
SessionType = Literal["Practice 1","Practice 2","Practice 3","Qualifying","Sprint","Race","Sprint Qualifying","Sprint Shootout"]
Flag = Literal["GREEN","YELLOW","RED","SC","VSC","CHEQUERED","UNKNOWN"]

class DriverInfo(BaseModel):
    driver_number: int
    abbreviation: str
    full_name: str
    team_name: str
    team_colour: Optional[str] = None
    headshot_url: Optional[str] = None

class CircuitInfo(BaseModel):
    circuit_key: str
    circuit_name: str
    country: str
    location: str
    round: Optional[int] = None
    lap_length_km: Optional[float] = None
    laps: Optional[int] = None
    # Per-circuit calibration (fitted from historical data)
    degradation_multiplier: float = 1.0
    pit_loss_seconds: float = 22.0
    sc_probability_per_lap: float = 0.02

class LapRecord(BaseModel):
    driver_number: int
    lap_number: int
    lap_time_seconds: Optional[float] = None
    sector1: Optional[float] = None
    sector2: Optional[float] = None
    sector3: Optional[float] = None
    compound: Compound = "UNKNOWN"
    tyre_age: int = 0
    is_outlap: bool = False
    is_inlap: bool = False
    is_fastest: bool = False

class StintInfo(BaseModel):
    driver_number: int
    stint_number: int
    compound: Compound
    tyre_age_at_start: int = 0
    lap_start: int
    lap_end: Optional[int] = None

class CarState(BaseModel):
    driver_number: int
    position: Optional[int] = None
    gap_to_leader: Optional[str] = None
    interval: Optional[str] = None
    last_lap_time: Optional[float] = None
    compound: Compound = "UNKNOWN"
    tyre_age: int = 0
    stint: int = 1
    pit_stops: int = 0
    speed: Optional[float] = None  # km/h
    throttle: Optional[float] = None
    brake: Optional[float] = None
    gear: Optional[int] = None
    drs: Optional[int] = None
    rpm: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    status: str = "On Track"

class RaceState(BaseModel):
    session_key: str
    session_name: str
    session_type: str = "Race"
    circuit: Optional[CircuitInfo] = None
    flag: Flag = "GREEN"
    lap: int = 0
    total_laps: Optional[int] = None
    elapsed_seconds: float = 0.0
    cars: List[CarState] = []
    race_control_messages: List[str] = []
    weather: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SimulationRequest(BaseModel):
    circuit_key: str = Field(default="monza", description="Circuit identifier")
    total_laps: int = Field(default=53, ge=1, le=100)
    drivers: Optional[List[DriverInfo]] = None
    strategies: Optional[List[Dict[str, Any]]] = None  # e.g. [{"driver_number":1,"compounds":["SOFT","MEDIUM"],"pit_laps":[20]}]
    # Physics params (can override per-circuit defaults)
    base_lap_time: float = 85.0  # seconds
    fuel_effect_per_kg: float = 0.03
    fuel_load_kg: float = 92.5
    track_temp_c: float = 35.0
    air_temp_c: float = 25.0
    n_simulations: int = Field(default=5000, ge=100, le=20000)
    seed: Optional[int] = 42
    include_safety_car: bool = True

class SimulationResult(BaseModel):
    strategy_id: str
    compounds: List[str]
    pit_laps: List[int]
    mean_total_time: float
    median_total_time: float
    std_total_time: float
    p5_total_time: float
    p95_total_time: float
    fastest_time: float
    slowest_time: float
    win_probability: float
    podium_probability: float
    points_probability: float
    samples: Optional[List[float]] = None  # optional histogram

class SimulationResponse(BaseModel):
    request: SimulationRequest
    results: List[SimulationResult]
    best_strategy_id: str
    compute_ms: int
    meta: Dict[str, Any] = {}
