# Architecture — F1 Advanced Race Simulation Platform

## Vision
> Real-time, physics-accurate F1 race simulation that beats naive models on MAE, predicts strategy windows, and visualizes live with <100ms dashboard latency.

## High-Level Diagram

```
                         ┌─────────────────────────────────────────────────────────────┐
                         │                    DATA SOURCES                              │
                         │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
                         │  │ Jolpica  │ │  FastF1  │ │  OpenF1  │ │ F1 LiveTiming│  │
                         │  │ 1950→Now │ │2018→Now  │ │ 2023→Now │ │  SignalR     │  │
                         │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘  │
                         └───────┼────────────┼────────────┼──────────────┼──────────┘
                                 │            │            │              │
                         ┌───────▼────────────▼────────────▼──────────────▼──────────┐
                         │              INGESTION LAYER (Python)                       │
                         │  openf1_client.py  jolpica_client.py  fastf1_service.py  │
                         │  live_ingest.py ──► Unified RaceEvent schema ──► Redis    │
                         └──────────────────────────┬────────────────────────────────┘
                                                    │
                         ┌──────────────────────────▼────────────────────────────────┐
                         │              CORE SERVICES (FastAPI)                        │
                         │  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │
                         │  │ Race State  │ │  Simulation  │ │   ML Models      │  │
                         │  │  Reducer    │ │   Engine     │ │ LightGBM + LSTM  │  │
                         │  │(merge+fold) │ │Physics+MC    │ │ degradation/pred │  │
                         │  └──────┬──────┘ └──────┬───────┘ └────────┬─────────┘  │
                         │         └───────────────┼──────────────────┘              │
                         │  ┌──────────────────────▼──────────────────────┐           │
                         │  │        Strategy Optimizer (DP + MC)        │           │
                         │  └──────────────────────┬──────────────────────┘           │
                         └──────────────────────────┼────────────────────────────────┘
                                                    │ WebSocket @10Hz + REST
                         ┌──────────────────────────▼────────────────────────────────┐
                         │              FRONTEND (React + Vite)                        │
                         │  Track Map (SVG/Three.js) │ Timing Tower │ Telemetry      │
                         │  Strategy Panel │ Race Control │ Pit Predictor            │
                         └────────────────────────────────────────────────────────────┘
```

## Components

### 1. Ingestion Layer (`backend/app/services/`)

- **JolpicaClient** — historical schedules, results, standings, qualifying. Cached 24h.
- **OpenF1Client** — live/ historical laps, car_data, location, stints, weather, team_radio. Polling 3s + optional MQTT.
- **FastF1Service** — session cache, telemetry DataFrames, circuit info. Heavy, used for pre-race fitting.
- **Unified Schema** — `RaceEvent`, `CarState`, `RaceState` (Pydantic). All feeds fold into this via `reducer.py`.
- **LiveIngest** — async loop: poll OpenF1 → delta-merge → Redis publish. Fallback to replay file if offline.

### 2. Simulation Engine (`backend/app/simulation/`)

| Module | Purpose | Key Formula |
|---|---|---|
| `physics.py` | Tyre + fuel + aero + track | `lap_time = base + offset_c + wear·age·(1+φ·fuel) + q·age² − fuel_burn·lap + ε` |
| `tyre.py` | Bayesian quadratic degradation | `μ = α + β·age + γ·age²`, γ≥0, compound priors, MCMC/NUTS fit |
| `fuel.py` | Fuel correction | `corrected = raw − (total_laps − lap +1)·kg_per_lap·0.03` |
| `track.py` | Circuit-specific params | Degradation multiplier, pit loss, SC hazard per circuit (from TUM DB) |
| `monte_carlo.py` | Vectorized 10k sims | AR(1) noise, pit loss LogNormal, SC Poisson, reactive policy |
| `strategy.py` | DP optimizer | Exact DP over compound sequences + pit windows, ranked by expected time / win prob |

### 3. ML Models (`backend/app/models/`)

- **DegradationModel** — LightGBM regressor on (compound, age, track_temp, circuit_id) → lap_time delta. Trained on FastF1 archives.
- **NextLapPredictor** — LSTM (optional) for next-lap forecast, +13% vs persistence target.

### 4. API Layer (`backend/app/api/`)

- `GET /api/health` — health + data source status
- `GET /api/sessions?year=` — list sessions (Jolpica+OpenF1)
- `GET /api/session/{year}/{round}/{session}` — session details
- `GET /api/telemetry/{session_key}/{driver}` — telemetry
- `POST /api/simulate` — run Monte Carlo simulation
- `POST /api/strategy/optimize` — find optimal strategy
- `WS /ws/live/{session_key}` — 10Hz live feed
- `WS /ws/simulation` — simulation progress streaming

### 5. Frontend (`frontend/`)

- **Vite + React 18 + TypeScript + Tailwind**
- **Track Map** — SVG from GeoJSON (bacinger/f1-circuits) + real X/Y interpolation, 60fps rAF, zoom/pan, battle lines.
- **Timing Tower** — positions, gaps, intervals, tyre, pit count, fastest lap, DRS.
- **Telemetry Charts** — Recharts: speed/throttle/brake vs distance, driver overlay.
- **Strategy Panel** — Monte Carlo distribution (KDE/histogram), pit window, win probability.
- **Race Control** — flags, investigations, penalties.
- Design: dark F1-inspired, carbon fiber, team colors.

## Data Flow — Real-Time Path

1. User opens `Race Replay` → frontend fetches session via `GET /api/session` (Jolpica+FastF1).
2. Live race: `LiveIngest` polls OpenF1 every 3s → `reducer` merges delta → Redis → WebSocket @10Hz → frontend interpolates @60fps.
3. Offline/replay: backend streams archived telemetry at configurable speed (1×–64×) via same WebSocket.
4. Strategy: frontend calls `POST /api/simulate` → Monte Carlo runs server-side → returns distributions → renders.

## Deployment

- **Dev**: `docker-compose up` — FastAPI (8000), Redis (6379), Frontend (5173)
- **Prod**: Same + Nginx, or Vercel (frontend) + Render/Fly (backend)
- **No Redis fallback**: in-memory pub/sub if Redis unavailable (dev mode)

## Accuracy Improvements — Summary

- Quadratic degradation with γ≥0 (no phantom speed-up)
- Fuel correction decoupled from tyre age via stint resets
- Per-circuit calibration (degradation, pit loss, SC hazard)
- AR(1) noise (correlated laps, not independent)
- Bayesian posteriors → uncertainty quantification (P95, CVaR)
- Walk-forward backtesting, MAE dashboards
- Reactive SC policy (pit under neutralisation inside window)

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic, NumPy, Pandas, SciPy, scikit-learn, LightGBM (optional), FastF1, httpx, websockets, Redis
- **Frontend**: Vite, React, TypeScript, Tailwind, Recharts, Three.js (optional), Framer Motion
- **Infra**: Docker, docker-compose, GitHub Actions (future)
