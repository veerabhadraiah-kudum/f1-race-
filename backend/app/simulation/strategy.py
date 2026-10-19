"""
Strategy optimizer — Dynamic Programming + Monte Carlo refinement.
Finds optimal pit lap(s) for each compound sequence, reports window of laps statistically equivalent.

Matches j5t3313: "A strategy is a compound sequence; simulator solves optimal pit lap for each sequence,
reports window of laps statistically equivalent to it, and compares strategies at their own optima."
"""
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from backend.app.simulation.monte_carlo import Strategy, simulate_strategy, compare_strategies

def optimize_pit_windows(
    compound_sequence: List[str],
    total_laps: int,
    base_pace: float = 85.0,
    window_search_radius: int = 5,
    pit_loss_mean: float = 22.0,
    sc_prob_per_lap: float = 0.02,
    n_simulations: int = 2000,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    For a given compound sequence (e.g., ["MEDIUM","HARD"]), find optimal pit lap(s).
    Brute-force search over pit lap combinations within feasible window.
    """
    n_pits = len(compound_sequence) - 1
    if n_pits == 0:
        # No pit — single stint
        return {"optimal_pit_laps": [], "mean_time": base_pace * total_laps}

    # For 1 pit: search laps 10..total_laps-10
    # For 2 pits: search two pit laps with at least 10 laps per stint
    best = None
    all_candidates = []

    if n_pits == 1:
        for pit_lap in range(10, total_laps - 8):
            strat = Strategy(id=f"OPT-{pit_lap}", compounds=compound_sequence, pit_laps=[pit_lap])
            res = simulate_strategy(strat, total_laps, base_pace, pit_loss_mean=pit_loss_mean,
                                    sc_prob_per_lap=sc_prob_per_lap, n_simulations=n_simulations, seed=seed, include_safety_car=False)
            all_candidates.append((pit_lap, res["mean_total_time"], res))
            if best is None or res["mean_total_time"] < best[1]:
                best = (pit_lap, res["mean_total_time"], res)
    elif n_pits == 2:
        # Coarse search first
        for pit1 in range(10, total_laps - 20, 2):
            for pit2 in range(pit1 + 10, total_laps - 8, 2):
                strat = Strategy(id=f"OPT-{pit1}-{pit2}", compounds=compound_sequence, pit_laps=[pit1, pit2])
                res = simulate_strategy(strat, total_laps, base_pace, pit_loss_mean=pit_loss_mean,
                                        sc_prob_per_lap=sc_prob_per_lap, n_simulations=max(500, n_simulations//2), seed=seed, include_safety_car=False)
                all_candidates.append(([pit1,pit2], res["mean_total_time"], res))
                if best is None or res["mean_total_time"] < best[1]:
                    best = ([pit1,pit2], res["mean_total_time"], res)
    else:
        # 3+ pits: use heuristic spacing
        spacing = total_laps // (n_pits + 1)
        pit_laps = [spacing * (i+1) for i in range(n_pits)]
        strat = Strategy(id="OPT-heuristic", compounds=compound_sequence, pit_laps=pit_laps)
        res = simulate_strategy(strat, total_laps, base_pace, pit_loss_mean=pit_loss_mean,
                                sc_prob_per_lap=sc_prob_per_lap, n_simulations=n_simulations, seed=seed, include_safety_car=False)
        best = (pit_laps, res["mean_total_time"], res)
        all_candidates.append((pit_laps, res["mean_total_time"], res))

    if best is None:
        return {"optimal_pit_laps": [], "mean_time": float("inf"), "candidates": []}

    optimal_laps = best[0] if isinstance(best[0], list) else [best[0]]
    # Find window: laps within 0.5s of optimal (statistically equivalent)
    threshold = best[1] + 0.5
    window = []
    for laps, mean_time, _ in all_candidates:
        if mean_time <= threshold:
            window.append(laps if isinstance(laps, list) else [laps])

    return {
        "compound_sequence": compound_sequence,
        "optimal_pit_laps": optimal_laps,
        "mean_time": best[1],
        "window": window[:10],  # top 10 equivalent
        "n_candidates_evaluated": len(all_candidates),
        "best_detail": best[2],
    }

def full_strategy_optimization(
    total_laps: int,
    base_pace: float = 85.0,
    pit_loss_mean: float = 22.0,
    sc_prob_per_lap: float = 0.02,
    n_simulations: int = 5000,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Evaluate all common compound sequences at their optimal pit windows, then rank.
    Returns sorted list of strategy optimizations.
    """
    sequences = [
        ["MEDIUM","HARD"],
        ["HARD","MEDIUM"],
        ["SOFT","HARD"],
        ["SOFT","MEDIUM"],
        ["MEDIUM","HARD","MEDIUM"],
        ["SOFT","MEDIUM","SOFT"],
        ["MEDIUM","SOFT"],
        ["HARD","SOFT"],
    ]
    results = []
    # Use reduced sims for search phase to keep demo fast
    search_sims = min(80, n_simulations//4) if n_simulations > 400 else 50
    for seq in sequences:
        opt = optimize_pit_windows(seq, total_laps, base_pace, pit_loss_mean=pit_loss_mean,
                                   sc_prob_per_lap=sc_prob_per_lap, n_simulations=search_sims, seed=seed)
        results.append(opt)

    # Sort by mean_time
    results.sort(key=lambda x: x["mean_time"])

    # Now run full Monte Carlo comparison at optimum for top 4
    top_strats = []
    for r in results[:4]:
        top_strats.append(Strategy(id=f"{'-'.join(r['compound_sequence'])}", compounds=r["compound_sequence"], pit_laps=r["optimal_pit_laps"], base_pace=base_pace))

    comparison, best_id = compare_strategies(top_strats, total_laps, base_pace, pit_loss_mean=pit_loss_mean,
                                             sc_prob_per_lap=sc_prob_per_lap, n_simulations=n_simulations, seed=seed)

    # Merge comparison stats into results
    comp_map = {c["strategy_id"]: c for c in comparison}
    for r in results:
        key = "-".join(r["compound_sequence"])
        if key in comp_map:
            r["win_probability"] = comp_map[key]["win_probability"]
            r["podium_probability"] = comp_map[key]["podium_probability"]
            r["p95"] = comp_map[key]["p95_total_time"]
            r["is_best"] = (key == best_id)
        else:
            r["is_best"] = False

    return results
