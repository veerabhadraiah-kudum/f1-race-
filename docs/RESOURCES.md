# F1 Advanced Simulation — Resource Gathering Report

> **Phase 0: Gather Resources Before Building**
> Date: 2026-10-19 | Author: F1 Race Simulation Team
> This document catalogues every GitHub repo, API, dataset, and tool evaluated before writing a single line of simulation code. “Better accurate results” starts with better data.

---

## 1. Decision Matrix — Which Stack to Use?

| Need | Candidate | Verdict | Why |
|---|---|---|---|
| **Historical results 1950-present** | Ergast (DEPRECATED Dec 2024), **Jolpica-F1** | ✅ **Jolpica-F1** | Drop-in Ergast replacement, community standard, FastF1 now points to `api.jolpi.ca/ergast/f1`. Ergast is dead — do not use. |
| **Timing + Telemetry 2018-present** | **FastF1 3.8.3** | ✅ **FastF1** | The de facto standard. Wraps official F1 live timing + Jolpica. Pandas DataFrames + Matplotlib + caching. MIT. 5.4k ⭐ |
| **Real-time live data (<3s delay)** | **OpenF1** | ✅ **OpenF1** | Free historical 2023+ JSON/CSV/MQTT/WebSocket. Real-time requires supporter tier but 3 req/s free is enough for demo. Independent of Ergast. |
| **Official live timing stream** | **LiveF1** (GoktugOcal), **matteocelani/f1-telemetry** (SignalR) | ✅ Both — LiveF1 for Python ETL, f1-telemetry for WebSocket decode | LiveF1 gives medallion-architecture ETL; matteocelani decodes official SignalR feed → WebSocket |
| **All-time database (CSV/SQLite)** | **F1DB** | ✅ F1DB | CSV, JSON, SQL, SQLite — drivers, constructors, circuits, pit stops, standings. Perfect for offline fallback. |
| **FIA document parsing** | **fia-doc** | ✅ | Extracts tyre compounds, classifications, lap times from official FIA PDFs — ground truth. |
| **Telemetry archives** | **TracingInsights/2026**, **formula1-datasets**, **renumics/f1_dataset** | ✅ All three | Season-by-season CSV/JSON, auto-updated <3h post-race. renumics has 882-dim embeddings for ML. |
| **Track geometry** | **bacinger/f1-circuits** (GeoJSON), **TUMFTM/racetrack-database** | ✅ Both | 77 historic circuits + per-point width + computed race line. Essential for accurate physics. |
| **Live dashboard reference** | **slowlydev/f1-dash** (1.9k ⭐, Rust+Next.js) | ✅ Study | Real-time dashboard — inspiration for frontend WebSocket design. |
| **3D Visualization** | **jamie005/f1-race-replay** (Kafka+Protobuf+Cesium), **adn8naiagent/F1ReplayTiming** (Next.js+FastAPI) | ✅ Study both | Cesium/Resium for 3D globe, Three.js/WebGPU for track. Best-in-class replay. |

---

## 2. Curated GitHub Repos — By Category

### 2.1 APIs & Libraries (Data Access)

| Repo | Stars | Stack | What it gives | Link |
|---|---|---|---|---|
| **theOehrly/Fast-F1** | 5.4k | Python | Timing, telemetry, weather, sessions, strategy. Caching + Pandas + Matplotlib | https://github.com/theOehrly/Fast-F1 |
| **br-g/openf1** | — | REST/MQTT/WS | Lap timings, car telemetry (throttle/brake/DRS/gear), team radio, stints, weather, positions | https://github.com/br-g/openf1 |
| **jolpica/jolpica-f1** | — | REST | Ergast-compatible: schedules, results, qualifying, standings 1950-present | https://github.com/jolpica/jolpica-f1 |
| **GoktugOcal/LiveF1** | — | Python | Real-time + historical via official live timing, medallion ETL | https://github.com/GoktugOcal/LiveF1 |
| **f1db/f1db** | — | CSV/SQL | All-time DB, circuits/layouts, pit stops, grids | https://github.com/f1db/f1db |
| **harningle/fia-doc** | — | Python | FIA PDF parsers — tyre compounds, classifications | https://github.com/harningle/fia-doc |
| **bccheung/tif1** | — | Python | Enriched post-session data, no rate limits | https://pypi.org/project/tif1/ |

### 2.2 Live Timing & Dashboards

| Repo | Stars | Stack | Highlight | Link |
|---|---|---|---|---|
| **slowlydev/f1-dash** | 1.9k | Rust+Next.js | Real-time dashboard, reference for WebSocket | https://github.com/slowlydev/f1-dash |
| **matteocelani/f1-telemetry** | — | Next.js/Node | Decodes official SignalR → WebSocket | https://github.com/matteocelani/f1-telemetry |
| **adn8naiagent/F1ReplayTiming** | 857 | Next.js+FastAPI | Replay+live, track map @0.5s, pit prediction | https://github.com/adn8naiagent/F1ReplayTiming |
| **IAmTomShaw/f1-race-replay** | 6.7k | Python/Pygame | Interactive replay, safety car, insights menu | https://github.com/IAmTomShaw/f1-race-replay |
| **srujan911/F1RaceVision** | — | Python/Pygame+FastF1 | Real X/Y, leaderboard, telemetry panel | https://github.com/srujan911/F1RaceVision |
| **natcat38/f1-race-tracker** | — | Py+Go+Redis+React | 10Hz WebSocket, 1000 concurrent viewers p99 48ms | https://github.com/natcat38/f1-race-tracker |
| **MatthewDelong/F1-Telemetry** | — | React19/Vite+3D | Procedural 3D tracks from GPS, AR car viewer | https://github.com/MatthewDelong/F1-Telemetry |

### 2.3 Simulation & Strategy Engines (Core Inspiration)

| Repo | Focus | Model | Link |
|---|---|---|---|
| **Ark07Yad/pitwall** | Live strategy engine | Tyre α·age+γ·age², fuel physics, per-circuit SC hazard, Monte Carlo, logged & scored calls | https://github.com/Ark07Yad/pitwall |
| **RuchirBhatia4/Pitwall-AI** | 2026 season engine | Bayesian tyre, exact DP optimizer, Monte Carlo, hybrid physics+ML team behaviour, Next.js+FastAPI | https://github.com/RuchirBhatia4/Pitwall-AI |
| **j5t3313/f1-strategy-sim** | 2026 Bayesian | α+β·lap+γ·lap² with MCMC, AR(1) noise, FP2 pipeline via FastF1 | https://github.com/j5t3313/f1-strategy-sim |
| **404soulnotfound/boxbox-f1** | Real-time strategy | LightGBM degradation + 10k Monte Carlo <200ms + undercut detector | https://github.com/404soulnotfound/boxbox-f1 |
| **shaxammm/f1-race-strategy-simulator** | Educational Monte Carlo | Streamlit, tyre/fuel/weather/SC, reproducible seeds | https://github.com/shaxammm/f1-race-strategy-simulator |
| **Sanaullah-Turab/F1-Simulator (RaceBox)** | Full-stack analytics | Race Wall, Strategy Engine, Monte Carlo, Telemetry, Championship | https://github.com/Sanaullah-Turab/F1-Simulator |
| **james-gasp/F1-Race-Strategy** | Pit strategy | OLS pace model (driver+compound+fuel+degradation), pit loss median, full-field Monte Carlo | https://github.com/james-gasp/F1-Race-Strategy |
| **NarekGrigoryan2008/f1-strategy-engine** | Decision support | Validated vs 150 races (2018-2026), logistic regression, DNF/SC/weather | https://github.com/NarekGrigoryan2008/f1-strategy-engine |
| **ssergio05/f1_strategy_sim** | C++20 engine | High-performance C++ Monte Carlo + Python visualization | https://github.com/ssergio05/f1_strategy_sim |

### 2.4 3D / Track Visualization

| Repo | Stack | Link |
|---|---|---|
| **jamie005/f1-race-replay** | React+Cesium/Resium+Kafka+Protobuf | https://github.com/jamie005/f1-race-replay |
| **Makakashan/F1TrackViewer** | Next.js16+Three.js+R3F, 40+ tracks, globe picker | https://github.com/Makakashan/F1TrackViewer |
| **yashyegare/F1TrackMetricsLab** | WebGL road ribbon, elevation banking, speed heatmap | https://github.com/yashyegare/F1TrackMetricsLab |
| **pgrinste/motorsport-telemetry** | Physics ideal line + GPU Monte Carlo (4096 samples) in CesiumJS | https://github.com/pgrinste/motorsport-telemetry |

### 2.5 Datasets & Telemetry Archives

| Source | Coverage | Format | Link |
|---|---|---|---|
| **TracingInsights/2026** | 2026 season | JSON per session (drivers, race control, corners, laps, weather) | https://github.com/TracingInsights/2026 |
| **TracingInsights HuggingFace** | Full Ergast mirror | 20+ CSV, auto-updated <3h post-race | https://huggingface.co/datasets/TracingInsights |
| **formula1-datasets** | 2019-2026 | CSV + Jupyter notebooks per season | https://github.com/formula1-datasets |
| **renumics/f1_dataset** | Montreal 2023 | 40+ cols + 882-dim embeddings | https://huggingface.co/datasets/renumics/f1_dataset |
| **bacinger/f1-circuits** | 35+/77 circuits | GeoJSON | https://github.com/bacinger/f1-circuits |
| **TUMFTM/racetrack-database** | 20+ circuits | Center line, width, race line | https://github.com/TUMF/TM-racetrack-database |

### 2.6 Awesome List

| Repo | Link |
|---|---|
| **subinium/awesome-f1** — curated collection of APIs, datasets, telemetry, sim racing | https://github.com/subinium/awesome-f1 |

---

## 3. Data Flow Chosen for This Project

```
F1 Live Timing (SignalR) ──┐
                           ├──► LiveF1 / OpenF1 API ──► Python Ingest (FastAPI) ──► Redis (pub/sub) ──► Go Gateway / FastAPI WebSocket ──► React Dashboard
Jolpica-F1 (historical) ───┤                                              │
FastF1 (telemetry cache) ──┘                                              └──► Simulation Engine (Physics + Monte Carlo)
                                                                          │
FIA PDFs (fia-doc) ──► Validation GT                                      └──► ML Models (LightGBM/LSTM) ──► Strategy Optimizer
```

**Why this is “better accurate”:**
- Jolpica gives decades of ground truth for backtesting.
- FastF1 gives sub-second telemetry (speed, throttle, brake, gear, DRS, X/Y) — not just lap times.
- OpenF1 gives real-time positions @ ~3s latency, team radio, weather.
- LiveF1 / SignalR gives the authoritative feed — same as official timing screens.
- Fusing all four lets us cross-validate and fill gaps (e.g., if OpenF1 lags, FastF1 cache fills in).

---

## 4. Simulation Accuracy — What Prior Art Taught Us

| Lesson | Source | How we apply |
|---|---|---|
| **Quadratic degradation** `μ = α + β·lap + γ·lap²` — linear wear early, cliff later. γ ≥ 0 constraint. | j5t3313, Ark07Yad | Our `TyreModel` enforces γ≥0, compound-specific priors |
| **Fuel correction is non-negotiable** — tyre age resets at pit, lap number doesn't → fuel burn identifiable (0.04-0.07s/lap, ~0.03s/kg) | RuchirBhatia4, pyyroo-a | `fuel.py`: `corrected = raw - (laps_remaining)·kg_per_lap·0.03`, ~92.5kg start 2026 |
| **AR(1) autocorrelated noise**, not i.i.d. | j5t3313 | `monte_carlo.py` uses AR(1) per stint |
| **Per-circuit Safety Car hazard table + opening-lap spike**, not flat constant | mannytheawesome (12.9% DNF measured, not 4%) | `safety_car.py` with per-circuit Poisson |
| **Pit loss = median(inlap+outlap − predicted clean lap)** — robust to outliers | james-gasp | `pit.py` |
| **Walk-forward validation** — fit on earlier 2026 races, test on later, not random split | RuchirBhatia4, NarekGrigoryan2008 (150 races) | `validation/` with leave-one-race-out MAE tracking |
| **10k Monte Carlo <200ms** via vectorization | boxbox-f1 | NumPy vectorized, optional Numba |
| **Reactive pit policy under SC/VSC** | RuchirBhatia4 | Simulator re-evaluates strategy at neutralisation |

**Accuracy targets (from prior art benchmarks):**
- Degradation model: **0.054s/lap MAE** leave-one-race-out (ShivekRanjan)
- LSTM next-lap: **+13.1% vs persistence** (16 unseen 2026 races)
- Strategy engine: **74.1% accuracy / 0.765 AUC** (NarekGrigoryan)
- Pitwall: every call **logged, committed pre-lap, scored vs reality**

We adopt the same logging discipline: every simulated decision is timestamped pre-lap.

---

## 5. Legal & Rate Limits

| API | Rate Limit | Auth | Note |
|---|---|---|---|
| **Jolpica-F1** | generous, no auth for historical | None | Ergast-compatible, `https://api.jolpi.ca/ergast/f1/` |
| **OpenF1** | 3 req/s, 30 req/min (free), 2× for supporters | Optional | Real-time needs supporter for MQTT/WS; historical free |
| **FastF1** | Ergast/Jolpica limits: 4 req/s burst, 500/hr | None | Cache mitigates; live timing via separate endpoint |
| **F1 Live Timing** | unofficial, use politely | None | FastF1's built-in recorder; don't hammer |

> All repos above are MIT/Apache/AGPL — we respect licenses and attribute. No proprietary F1 data is redistributed; we fetch at runtime or cache locally.

---

## 6. Next Steps (Build Phase)

1. **Data Ingestion Layer** — `backend/app/services/` with OpenF1, Jolpica, FastF1 clients + unified schema + Redis pub/sub
2. **Physics Engine** — `backend/app/simulation/` tyre+fuel+track+weather
3. **Monte Carlo Simulator** — vectorized 10k runs, strategy optimizer
4. **ML Models** — LightGBM degradation, LSTM next-lap (optional)
5. **Real-time API** — FastAPI + WebSocket, 10Hz fan-out
6. **Frontend** — React + Vite + Three.js/Cesium track map + Recharts telemetry + Tailwind
7. **Validation Harness** — backtest vs TracingInsights archives, MAE dashboards

Proceed to `docs/ARCHITECTURE.md` for system design.
