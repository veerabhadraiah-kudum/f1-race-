# Simulation Model — Physics + Monte Carlo

## Tyre Degradation

**Quadratic with cliff:**

```
μ(age) = α + β·age + γ·age²,  γ ≥ 0
```

- α: compound offset (SOFT −0.6s, MEDIUM 0s, HARD +0.5s)
- β: linear wear (SOFT 0.08, MEDIUM 0.05, HARD 0.03 s/lap)
- γ: cliff (SOFT 0.003, MEDIUM 0.0015, HARD 0.0008)
- σ: residual std ~0.30s, AR(1) ρ≈0.30
- Temperature: +1.5% per °C above 30°C
- Per-circuit multiplier: Monza 0.85× … Barcelona 1.25×

Fitted via constrained least squares (γ≥0) or Bayesian MCMC (informative priors). See `tyre.py`.

## Fuel

```
corrected = raw − (laps_remaining)·kg_per_lap·0.03
fuel_remaining(lap) = start − (lap−1)·kg_per_lap
```

Start 92.5kg (89.5+3 reserve), ~1.6 kg/lap, 0.03 s/kg. Identifiable because tyre age resets at pit, lap number doesn't.

## Lap Time Assembly

```
t = base_d + offset_c + wear·a·(1+φ·fuel) + q·a² − fuel_burn·n + evolution + drs + cold + ε
```

- evolution: −0.005s/lap (rubbering), capped −0.4s
- drs: −0.25s when available (~60% laps after lap 3)
- cold: +1.2s outlap

## Monte Carlo Engine

For each simulation (vectorized 10k):

1. Draw base pace `N(0,0.4)`
2. Draw compound params from priors/circuit multiplier
3. Generate AR(1) noise per stint: `ε_t = ρ·ε_{t−1} + √(1−ρ²)·z_t`
4. Draw pit loss `LogNormal(μ=log(22), σ≈0.05)` — heavy-tailed
5. Draw SC events `Poisson(sc_prob·total_laps)`, up to 2, each saves 6–12s if in window (reactive policy)

Head-to-head ranking per sim → win%/podium%/points%.

Reported: mean, median, σ, P5, P95, fastest, slowest, win/podium.

## Strategy Optimizer

1. For each compound sequence (8 presets), brute-force pit lap search (35 candidates for 1-stop) at low sims (50)
2. Find optimal lap(s) minimizing mean total time
3. Compute window: laps within +0.5s of optimal
4. Re-run top 4 at full sims for win% via `compare_strategies`

## Validation

- Leave-one-race-out MAE (target 0.054s/lap)
- Walk-forward: train on races 1..k, test on k+1
- Every call logged pre-lap, scored post-race

