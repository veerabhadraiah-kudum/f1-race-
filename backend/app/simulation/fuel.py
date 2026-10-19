"""
Fuel correction model.
2026 regulation: 3000 MJ/h energy flow cap, no mandated race fuel mass.
We use observed start load ~92.5kg (89.5 usable + 3kg reserve).
Fuel burn identifiable because tyre age resets at pit, lap number doesn't.

lap_time_corrected = raw_lap_time - (laps_remaining) * kg_per_lap * weight_effect
weight_effect ~0.03 s/kg (0.04-0.07 s/lap empirically)
"""
from dataclasses import dataclass

@dataclass
class FuelModel:
    total_laps: int
    start_fuel_kg: float = 92.5
    fuel_per_lap_kg: float = 1.6  # ~92.5/57 laps ≈1.62
    weight_effect_s_per_kg: float = 0.03  # seconds per kg
    reserve_kg: float = 3.0

    def __post_init__(self):
        if self.fuel_per_lap_kg is None:
            usable = self.start_fuel_kg - self.reserve_kg
            self.fuel_per_lap_kg = usable / max(1, self.total_laps) if self.total_laps else 1.6

    def fuel_remaining(self, lap: int) -> float:
        """Fuel remaining at START of lap (1-indexed)."""
        consumed = max(0, lap - 1) * self.fuel_per_lap_kg
        return max(self.reserve_kg, self.start_fuel_kg - consumed)

    def fuel_correction(self, lap: int) -> float:
        """Time penalty due to fuel mass at this lap (to be SUBTRACTED for correction)."""
        return self.fuel_remaining(lap) * self.weight_effect_s_per_kg

    def corrected_lap_time(self, raw_lap_time: float, lap: int) -> float:
        """Remove fuel effect to isolate tyre performance."""
        return raw_lap_time - self.fuel_correction(lap)

    def add_fuel_back(self, base_lap_time: float, lap: int) -> float:
        """Re-add fuel penalty to get on-track lap time."""
        return base_lap_time + self.fuel_correction(lap)

def estimate_fuel_per_lap(total_fuel: float = 92.5, total_laps: int = 57, reserve: float = 3.0) -> float:
    return (total_fuel - reserve) / max(1, total_laps)
