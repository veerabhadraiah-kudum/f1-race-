import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.simulation.monte_carlo import Strategy, simulate_strategy, compare_strategies
from backend.app.services.unified import get_circuit_info

def test_tyre_degradation_increases():
    from backend.app.simulation.tyre import get_tyre_params, tyre_degradation_seconds
    p = get_tyre_params("MEDIUM", 35.0, 1.0)
    d1 = tyre_degradation_seconds(1, p)
    d10 = tyre_degradation_seconds(10, p)
    d20 = tyre_degradation_seconds(20, p)
    assert d10 > d1
    assert d20 > d10

def test_fuel_decreases():
    from backend.app.simulation.fuel import FuelModel
    f = FuelModel(total_laps=53)
    assert f.fuel_remaining(1) > f.fuel_remaining(27)
    assert f.fuel_remaining(53) >= f.reserve_kg

def test_simulate_strategy_runs():
    from backend.app.simulation.monte_carlo import Strategy, simulate_strategy
    strat = Strategy(id="M-H", compounds=["MEDIUM","HARD"], pit_laps=[27])
    res = simulate_strategy(strat, 53, 85.0, n_simulations=100, seed=0)
    assert res["mean_total_time"] > 0
    assert res["p95_total_time"] > res["p5_total_time"]
    assert res["compute_ms"] >= 0

def test_compare_strategies_win_sums_to_one():
    c = get_circuit_info("monza")
    from backend.app.simulation.monte_carlo import preset_strategies, compare_strategies
    strats = preset_strategies(53, "monza")
    results, best = compare_strategies(strats, 53, 85.0, c.degradation_multiplier, c.pit_loss_seconds, c.sc_probability_per_lap, 200, 42)
    total_win = sum(r["win_probability"] for r in results)
    assert abs(total_win - 1.0) < 1e-6
    assert best in [r["strategy_id"] for r in results]

def test_circuit_calibration():
    from backend.app.services.unified import CIRCUIT_CALIBRATION
    assert "monza" in CIRCUIT_CALIBRATION
    assert "monaco" in CIRCUIT_CALIBRATION
    assert CIRCUIT_CALIBRATION["monza"]["pit_loss_seconds"] > 15
