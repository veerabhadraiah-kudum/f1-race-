#!/usr/bin/env python3
"""
Demo: Run F1 race simulation offline — no API keys, no network required.
Shows:
- Single strategy Monte Carlo
- Multi-strategy comparison with win probabilities
- Strategy optimization (optimal pit windows)

Usage:
  python scripts/demo_simulation.py
  python scripts/demo_simulation.py --circuit monaco --laps 78 --sims 2000
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.simulation.monte_carlo import Strategy, compare_strategies, simulate_strategy, preset_strategies
from backend.app.simulation.strategy import optimize_pit_windows, full_strategy_optimization
from backend.app.services.unified import get_circuit_info

def print_result(r):
    print(f"  {r['strategy_id']:12s} | {str(r['compounds']):25s} pits@{r['pit_laps']} | "
          f"mean={r['mean_total_time']:7.1f}s median={r['median_total_time']:7.1f}s "
          f"σ={r['std_total_time']:4.1f} p95={r['p95_total_time']:7.1f} win={r['win_probability']:.1%}")

def main():
    parser = argparse.ArgumentParser(description="F1 Advanced Simulation Demo")
    parser.add_argument("--circuit", default="monza", help="Circuit key (monza, monaco, silverstone, etc.)")
    parser.add_argument("--laps", type=int, default=None, help="Total laps (default: circuit default)")
    parser.add_argument("--sims", type=int, default=3000, help="N simulations")
    args = parser.parse_args()

    circuit = get_circuit_info(args.circuit)
    total_laps = args.laps or circuit.laps
    print("\n🏎️  F1 ADVANCED RACE SIMULATION — OFFLINE DEMO")
    print("="*75)
    print(f"Circuit: {circuit.circuit_name} ({args.circuit}) | Laps: {total_laps} | Pit loss: {circuit.pit_loss_seconds}s | SC prob: {circuit.sc_probability_per_lap}")
    print(f"Degradation multiplier: {circuit.degradation_multiplier} | Lap length: {circuit.lap_length_km}km")
    print()

    # 1. Single strategy detail
    print("1️⃣  SINGLE STRATEGY — M→H 1-stop (Monte Carlo 3k runs)")
    print("-"*75)
    strat = Strategy(id="M-H", compounds=["MEDIUM","HARD"], pit_laps=[total_laps//2])
    res = simulate_strategy(strat, total_laps, base_pace=85.0, circuit_multiplier=circuit.degradation_multiplier,
                            pit_loss_mean=circuit.pit_loss_seconds, sc_prob_per_lap=circuit.sc_probability_per_lap,
                            n_simulations=args.sims, seed=42)
    print(f"  Mean: {res['mean_total_time']:.2f}s | Median: {res['median_total_time']:.2f}s | σ: {res['std_total_time']:.2f}")
    print(f"  P5: {res['p5_total_time']:.2f}s | P95: {res['p95_total_time']:.2f}s | Fastest: {res['fastest_time']:.2f} | Slowest: {res['slowest_time']:.2f}")
    print(f"  Compute: {res['compute_ms']}ms")
    print()

    # 2. Multi-strategy comparison
    print("2️⃣  MULTI-STRATEGY COMPARISON — win probabilities (head-to-head per sim)")
    print("-"*75)
    strategies = preset_strategies(total_laps, args.circuit)
    results, best = compare_strategies(strategies, total_laps, base_pace=85.0, circuit_multiplier=circuit.degradation_multiplier,
                                       pit_loss_mean=circuit.pit_loss_seconds, sc_prob_per_lap=circuit.sc_probability_per_lap,
                                       n_simulations=args.sims, seed=42)
    for r in sorted(results, key=lambda x: x['mean_total_time']):
        marker = " ⭐ BEST" if r['strategy_id']==best else ""
        print_result(r)
        print(f"               └─ podium={r['podium_probability']:.1%}{marker}")
    print(f"\n  → Best strategy: {best} (highest win probability)")
    print()

    # 3. Strategy optimization
    print("3️⃣  STRATEGY OPTIMIZATION — optimal pit windows for each compound sequence")
    print("-"*75)
    opts = full_strategy_optimization(total_laps, base_pace=85.0, pit_loss_mean=circuit.pit_loss_seconds,
                                      sc_prob_per_lap=circuit.sc_probability_per_lap, n_simulations=min(800, args.sims))
    for o in opts[:5]:
        seq = "-".join(o['compound_sequence'])
        star = " ⭐" if o.get('is_best') else ""
        print(f"  {seq:20s} pits@{o['optimal_pit_laps']} | mean={o['mean_time']:.1f}s win={o.get('win_probability',0):.1%} window={o['window'][:3]}{star}")
    print()

    # 4. Monaco vs Monza comparison
    print("4️⃣  CIRCUIT COMPARISON — why per-circuit calibration matters")
    print("-"*75)
    for ck in ["monaco","monza","barcelona"]:
        c = get_circuit_info(ck)
        print(f"  {ck:12s} deg_mult={c.degradation_multiplier:.2f} pit={c.pit_loss_seconds:.1f}s SC={c.sc_probability_per_lap:.3f}/lap laps={c.laps}")
    print()
    print("✅ Demo complete. Next: start API with `uvicorn backend.app.main:app --reload` and open http://localhost:8000/docs")
    print("   Frontend: cd frontend && npm install && npm run dev")
    print()

if __name__ == "__main__":
    main()
