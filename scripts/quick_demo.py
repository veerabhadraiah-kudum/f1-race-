#!/usr/bin/env python3
"""
Quick demo — fast, no timeout, proves simulation works.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.simulation.monte_carlo import Strategy, compare_strategies, simulate_strategy, preset_strategies
from backend.app.services.unified import get_circuit_info
from backend.app.simulation.strategy import optimize_pit_windows

circuit = get_circuit_info("monza")
total_laps = 53
print("🏎️  F1 Advanced Simulation — Quick Demo")
print(f"Circuit {circuit.circuit_name} pit={circuit.pit_loss_seconds}s deg_mult={circuit.degradation_multiplier}")
print()

# 1. Single strategy
strat = Strategy(id="M-H", compounds=["MEDIUM","HARD"], pit_laps=[27])
res = simulate_strategy(strat, total_laps, 85.0, circuit_multiplier=circuit.degradation_multiplier, pit_loss_mean=circuit.pit_loss_seconds, n_simulations=500, seed=42)
print(f"1) M-H 1-stop: mean={res['mean_total_time']:.1f}s median={res['median_total_time']:.1f}s σ={res['std_total_time']:.1f} p95={res['p95_total_time']:.1f} compute={res['compute_ms']}ms")

# 2. Multi-strategy
strats = preset_strategies(total_laps, "monza")
results, best = compare_strategies(strats, total_laps, 85.0, circuit_multiplier=circuit.degradation_multiplier, pit_loss_mean=circuit.pit_loss_seconds, n_simulations=500, seed=42)
print(f"\n2) Multi-strategy comparison (500 sims each): best={best}")
for r in sorted(results, key=lambda x: x['mean_total_time']):
    print(f"   {r['strategy_id']:8s} {str(r['compounds']):20s} @ {r['pit_laps']} mean={r['mean_total_time']:.1f}s win={r['win_probability']:.0%}")

# 3. Optimize one sequence
opt = optimize_pit_windows(["MEDIUM","HARD"], total_laps, 85.0, pit_loss_mean=circuit.pit_loss_seconds, n_simulations=80)
print(f"\n3) Optimize M-H: optimal pit lap {opt['optimal_pit_laps']} window {opt['window'][:3]}")

print("\n✅ Quick demo OK — full demo: python scripts/demo_simulation.py --sims 3000 --skip-optimize (or increase timeout)")
