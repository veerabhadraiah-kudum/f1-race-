"""
Unified data service — merges Jolpica + OpenF1 + FastF1 into single schema.
This is the single source of truth for the simulation engine.
"""
import logging
from typing import Dict, Any, List, Optional
from backend.app.services.jolpica_client import jolpica
from backend.app.services.openf1_client import openf1
from backend.app.core.schemas import CircuitInfo

logger = logging.getLogger(__name__)

# Per-circuit calibration table (fitted from historical data — see docs/RESOURCES.md)
# Values: degradation_multiplier, pit_loss_seconds, sc_probability_per_lap
CIRCUIT_CALIBRATION: Dict[str, Dict[str, float]] = {
    "monza": {"degradation_multiplier": 0.85, "pit_loss_seconds": 23.5, "sc_probability_per_lap": 0.015, "lap_length_km": 5.793, "laps": 53},
    "monaco": {"degradation_multiplier": 0.55, "pit_loss_seconds": 20.0, "sc_probability_per_lap": 0.035, "lap_length_km": 3.337, "laps": 78},
    "silverstone": {"degradation_multiplier": 1.05, "pit_loss_seconds": 22.8, "sc_probability_per_lap": 0.025, "lap_length_km": 5.891, "laps": 52},
    "spa": {"degradation_multiplier": 0.95, "pit_loss_seconds": 24.2, "sc_probability_per_lap": 0.030, "lap_length_km": 7.004, "laps": 44},
    "barcelona": {"degradation_multiplier": 1.25, "pit_loss_seconds": 22.0, "sc_probability_per_lap": 0.018, "lap_length_km": 4.675, "laps": 66},
    "suzuka": {"degradation_multiplier": 1.10, "pit_loss_seconds": 22.5, "sc_probability_per_lap": 0.022, "lap_length_km": 5.807, "laps": 53},
    "bahrain": {"degradation_multiplier": 1.15, "pit_loss_seconds": 23.0, "sc_probability_per_lap": 0.020, "lap_length_km": 5.412, "laps": 57},
    "melbourne": {"degradation_multiplier": 0.90, "pit_loss_seconds": 21.5, "sc_probability_per_lap": 0.028, "lap_length_km": 5.278, "laps": 58},
    "jeddah": {"degradation_multiplier": 0.95, "pit_loss_seconds": 21.0, "sc_probability_per_lap": 0.040, "lap_length_km": 6.174, "laps": 50},
    "miami": {"degradation_multiplier": 1.00, "pit_loss_seconds": 22.2, "sc_probability_per_lap": 0.025, "lap_length_km": 5.412, "laps": 57},
    "imola": {"degradation_multiplier": 1.05, "pit_loss_seconds": 23.0, "sc_probability_per_lap": 0.020, "lap_length_km": 4.909, "laps": 63},
    "hungaroring": {"degradation_multiplier": 1.20, "pit_loss_seconds": 21.8, "sc_probability_per_lap": 0.012, "lap_length_km": 4.381, "laps": 70},
    "zandvoort": {"degradation_multiplier": 1.10, "pit_loss_seconds": 21.0, "sc_probability_per_lap": 0.018, "lap_length_km": 4.259, "laps": 72},
    "austin": {"degradation_multiplier": 1.10, "pit_loss_seconds": 22.5, "sc_probability_per_lap": 0.020, "lap_length_km": 5.513, "laps": 56},
    "mexico": {"degradation_multiplier": 0.90, "pit_loss_seconds": 22.0, "sc_probability_per_lap": 0.022, "lap_length_km": 4.304, "laps": 71},
    "brazil": {"degradation_multiplier": 1.15, "pit_loss_seconds": 22.0, "sc_probability_per_lap": 0.030, "lap_length_km": 4.309, "laps": 71},
    "las_vegas": {"degradation_multiplier": 0.85, "pit_loss_seconds": 21.5, "sc_probability_per_lap": 0.025, "lap_length_km": 6.201, "laps": 50},
    "qatar": {"degradation_multiplier": 1.20, "pit_loss_seconds": 22.8, "sc_probability_per_lap": 0.015, "lap_length_km": 5.419, "laps": 57},
    "abu_dhabi": {"degradation_multiplier": 1.00, "pit_loss_seconds": 22.5, "sc_probability_per_lap": 0.015, "lap_length_km": 5.281, "laps": 58},
    "default": {"degradation_multiplier": 1.0, "pit_loss_seconds": 22.0, "sc_probability_per_lap": 0.02, "lap_length_km": 5.0, "laps": 55},
}

def get_circuit_info(circuit_key: str) -> CircuitInfo:
    key = circuit_key.lower().strip()
    cal = CIRCUIT_CALIBRATION.get(key, CIRCUIT_CALIBRATION["default"])
    return CircuitInfo(
        circuit_key=key,
        circuit_name=key.title(),
        country="Unknown",
        location=key.title(),
        lap_length_km=cal["lap_length_km"],
        laps=cal["laps"],
        degradation_multiplier=cal["degradation_multiplier"],
        pit_loss_seconds=cal["pit_loss_seconds"],
        sc_probability_per_lap=cal["sc_probability_per_lap"],
    )

async def fetch_session_bundle(year: int, round_num: Optional[int] = None) -> Dict[str, Any]:
    """
    Fetch a comprehensive session bundle: schedule + results + standings.
    Uses Jolpica as primary, OpenF1 as secondary.
    """
    result: Dict[str, Any] = {"year": year, "source": "jolpica+openf1"}
    # Jolpica schedule
    try:
        sched = await jolpica.get_schedule(year)
        result["schedule"] = sched
    except Exception as e:
        logger.warning(f"Jolpica schedule failed: {e}")
        result["schedule_error"] = str(e)

    # OpenF1 sessions for same year
    try:
        sessions = await openf1.get_sessions(year=year)
        result["openf1_sessions"] = sessions
        result["openf1_count"] = len(sessions)
    except Exception as e:
        logger.warning(f"OpenF1 sessions failed: {e}")
        result["openf1_error"] = str(e)

    # If round specified, fetch race results
    if round_num is not None:
        try:
            race = await jolpica.get_race_results(year, round_num)
            result["race_results"] = race
        except Exception as e:
            logger.warning(f"Jolpica race results failed: {e}")
            result["race_results_error"] = str(e)

    return result

# Mock fallback for offline dev
MOCK_DRIVERS = [
    {"driver_number": 1, "abbreviation": "VER", "full_name": "Max Verstappen", "team_name": "Red Bull Racing", "team_colour": "#0600EF"},
    {"driver_number": 16, "abbreviation": "LEC", "full_name": "Charles Leclerc", "team_name": "Ferrari", "team_colour": "#DC0000"},
    {"driver_number": 44, "abbreviation": "HAM", "full_name": "Lewis Hamilton", "team_name": "Mercedes", "team_colour": "#00D2BE"},
    {"driver_number": 63, "abbreviation": "RUS", "full_name": "George Russell", "team_name": "Mercedes", "team_colour": "#00D2BE"},
    {"driver_number": 11, "abbreviation": "PER", "full_name": "Sergio Perez", "team_name": "Red Bull Racing", "team_colour": "#0600EF"},
    {"driver_number": 55, "abbreviation": "SAI", "full_name": "Carlos Sainz", "team_name": "Ferrari", "team_colour": "#DC0000"},
    {"driver_number": 4, "abbreviation": "NOR", "full_name": "Lando Norris", "team_name": "McLaren", "team_colour": "#FF8700"},
    {"driver_number": 81, "abbreviation": "PIA", "full_name": "Oscar Piastri", "team_name": "McLaren", "team_colour": "#FF8700"},
    {"driver_number": 14, "abbreviation": "ALO", "full_name": "Fernando Alonso", "team_name": "Aston Martin", "team_colour": "#006F62"},
    {"driver_number": 18, "abbreviation": "STR", "full_name": "Lance Stroll", "team_name": "Aston Martin", "team_colour": "#006F62"},
]

MOCK_SESSION = {
    "year": 2024,
    "event_name": "Monaco Grand Prix",
    "circuit_key": "monaco",
    "session_name": "Race",
    "total_laps": 78,
    "drivers": MOCK_DRIVERS,
}
