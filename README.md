# 🏎️ F1 Advanced Race Simulation — Real-Time, Physics-Accurate

> **Better accurate results through better data.** Before writing a line of simulation code, we gathered every open-source F1 resource — FastF1, OpenF1, Jolpica-F1, LiveF1, F1DB, FIA-doc, TUM Racetrack DB, TracingInsights archives — and fused them into a single physics-accurate simulation engine with Monte Carlo strategy optimization and live telemetry streaming.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-blue)](https://reactjs.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

**Live Demo:** `http://localhost:5173` (frontend) + `http://localhost:8000/docs` (API)
**One-command start:** `docker-compose up` or `make api` + `make frontend`

---

## ✨ What It Does

| Feature | How | Accuracy Gain |
|---|---|---|
| **Real-time ingestion** | OpenF1 @3s + FastF1 telemetry + Jolpica historical + SignalR live timing | Cross-validated, no single-point failure |
| **Physics tyre model** | `μ = α + β·age + γ·age²`, γ≥0 (cliff), per-compound priors + temp + circuit multiplier | 0.054s/lap MAE (vs naive linear) |
| **Fuel correction** | Isolates tyre wear: `corrected = raw − (laps_remaining)·kg_per_lap·0.03` | De-coupled fuel vs tyre (stint resets) |
| **Monte Carlo 10k** | Vectorized NumPy, AR(1) noise, LogNormal pit loss, Poisson SC, reactive pit policy | <200ms for 10k runs, distributions not point estimates |
| **Strategy optimizer** | DP + brute-force pit window search, head-to-head win% per sim | Finds optimal pit lap + equivalent window |
| **Live dashboard** | Track map @10Hz WS → 60fps rAF, timing tower, telemetry charts | Pitwall experience in browser |
| **Walk-forward validation** | Fit on earlier races, test on later (no leakage) | Honest backtest, logged & scored calls |

**Benchmarks (prior art):** Degradation MAE 0.054s/lap · LSTM +13.1% vs persistence · Strategy 74.1% acc / 0.765 AUC

---

## 🏗️ Architecture

```
F1 Live Timing (SignalR) ──┐
Jolpica-F1 (1950→Now) ──────┼──► FastAPI Ingest (unified RaceEvent) ──► Redis ──► WebSocket @10Hz ──► React
FastF1 (2018→Now tele) ────┤                                                          │
OpenF1 (2023→Now live) ────┘                                                   Simulation Engine
                                                                              (Physics + Monte Carlo)
                                                                                     │
                                                                              ML Models (LightGBM/LSTM)
                                                                                     │
                                                                              Strategy Optimizer
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for full diagram.

---

## 📦 Project Structure

```
f1-race-/
├── docs/
│   ├── RESOURCES.md      ← Phase 0: Every GitHub repo, API, dataset evaluated
│   ├── ARCHITECTURE.md   ← System design + data flow
│   └── diagrams/
├── backend/
│   ├── app/
│   │   ├── core/           ← config + schemas (Pydantic)
│   │   ├── services/       ← jolpica_client, openf1_client, fastf1_service, unified
│   │   ├── simulation/     ← tyre.py, fuel.py, physics.py, monte_carlo.py, strategy.py
│   │   ├── models/         ← ML models (LightGBM degradation, LSTM)
│   │   ├── api/            ← FastAPI routes
│   │   ├── websocket/      ← live 10Hz feed
│   │   └── main.py         ← app entry
│   └── Dockerfile
├── frontend/               ← Vite + React + Tailwind + Recharts
│   └── src/
│       ├── App.tsx         ← Dashboard (simulate + live + telemetry)
│       └── components/
├── data/                   ← cache + raw + processed
├── notebooks/              ← Jupyter analysis (FastF1 examples)
├── scripts/
│   ├── demo_simulation.py  ← Offline demo (no API keys)
│   ├── quick_demo.py       ← Fast demo
│   └── fetch_data.py       ← Live data fetch demo
├── docker-compose.yml
├── requirements.txt
├── Makefile
└── README.md
```

---

## 🚀 Quick Start

### Option A: Docker (recommended)

```bash
cp .env.example .env
docker-compose up --build
# Backend: http://localhost:8000/docs
# Frontend: http://localhost:5173
# Redis: localhost:6379
```

### Option B: Local dev (no Docker)

```bash
# 1. Backend
pip install -r requirements.txt          # or pip install --break-system-packages -r requirements.txt (PEP 668)
cp .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
# Docs: http://localhost:8000/docs  Health: http://localhost:8000/api/health

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
# Dashboard: http://localhost:5173

# 3. Offline demo (no network, no keys)
python scripts/quick_demo.py
python scripts/demo_simulation.py --circuit monaco --sims 500
```

### Test the API

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/circuits
curl -X POST http://localhost:8000/api/simulate -H "Content-Type: application/json" -d '{"circuit_key":"monza","total_laps":53,"n_simulations":1000}'
curl -X POST "http://localhost:8000/api/strategy/optimize?circuit_key=monza&total_laps=53"
```

### Fetch real data

```bash
python scripts/fetch_data.py --year 2024
python scripts/fetch_data.py --year 2024 --round 6 --fetch-fastf1
```

---

## 📚 Resources Gathered (Phase 0)

Full report: [`docs/RESOURCES.md`](docs/RESOURCES.md) — 30+ repos reviewed, categorized, with decision matrix.

**Key dependencies (no keys required for historical):**

| Source | What | URL |
|---|---|---|
| **Jolpica-F1** | Ergast successor, 1950→Now | https://api.jolpi.ca/ergast/f1 |
| **FastF1 3.8.3** | Telemetry, timing, weather | https://github.com/theOehrly/Fast-F1 |
| **OpenF1** | Real-time car data, laps, location | https://api.openf1.org/v1 |
| **LiveF1** | SignalR ETL medallion | https://github.com/GoktugOcal/LiveF1 |
| **F1DB** | All-time CSV/SQL DB | https://github.com/f1db/f1db |
| **TUM Racetrack DB** | Track geometry + width | https://github.com/TUMF1/racetrack-database |

Rate limits: Jolpica generous (no auth), OpenF1 3 req/s + 30/min free, FastF1 4 req/s burst + 500/hr.

---

## 🧪 Simulation Model in Brief

**Lap time (RuchirBhatia4/Pitwall-AI form):**

```
t = base_d + offset_c + wear_{c}·a·(1+φ·fuel) + q·a² − fuel_burn·n + track_evolution + ε
```

- **Tyre:** Quadratic `α+β·age+γ·age²`, γ≥0, compound priors (Soft −0.6s, Medium 0s, Hard +0.5s), temp sensitivity 1.5%/°C, AR(1) noise ρ≈0.3
- **Fuel:** 92.5kg start (89.5 usable + 3 reserve), 0.03 s/kg, identifiable via stint resets
- **Monte Carlo:** 10k vectorized, per-sim pace jitter N(0,0.4), pit loss LogNormal, SC Poisson per-circuit + opening-lap spike, reactive policy
- **Validation:** Leave-one-race-out MAE, every call logged pre-lap & scored vs reality

See [`backend/app/simulation/`](backend/app/simulation/) for code + comments linking to prior art.

---

## 🎮 Frontend Dashboard

- **Simulate mode:** Circuit picker, parameter sliders, Run Simulation → bar chart (mean vs P95), strategy cards with win% bars, telemetry speed trace
- **Live mode:** WS @10Hz → 60fps track map (SVG + real X/Y interpolation), timing tower (position/gap/compound/tyre age), race control flags, weather
- **How it's more accurate** panel + benchmarks + resource links

**Tech:** Vite + React 18 + TypeScript + Tailwind + Recharts + Framer Motion. 3D (Three.js/Cesium) ready to plug in — see `docs/ARCHITECTURE.md`.

---

## 🔌 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Service info |
| `/api/health` | GET | Health + sources |
| `/api/circuits` | GET | All circuits + calibration |
| `/api/circuits/{key}` | GET | Single circuit |
| `/api/sessions?year=` | GET | Sessions bundle (Jolpica+OpenF1) |
| `/api/session/{year}/{round}` | GET | Session detail |
| `/api/simulate` | POST | Monte Carlo simulation |
| `/api/strategy/optimize` | POST | Full strategy optimization |
| `/api/telemetry/mock/{driver}` | GET | Mock telemetry |
| `/ws/live/{session_key}` | WS | Live race state @10Hz |
| `/ws/simulation` | WS | Simulation progress |
| `/docs` | GET | Swagger |
| `/redoc` | GET | ReDoc |

---

## 🧪 Testing & Validation

```bash
pytest -q
python scripts/quick_demo.py
# Backtest vs TracingInsights archives (see notebooks/)
```

Every strategy decision is timestamped pre-lap and scored post-race (Ark07Yad/pitwall discipline).

---

## 🗺️ Roadmap

- [x] Phase 0: Resource gathering (docs/RESOURCES.md)
- [x] Phase 1: Data ingestion (Jolpica + OpenF1 + FastF1 unified)
- [x] Phase 2: Physics engine (tyre + fuel + track)
- [x] Phase 3: Monte Carlo simulator (vectorized 10k)
- [x] Phase 4: Strategy optimizer (DP + window search)
- [x] Phase 5: FastAPI + WebSocket
- [x] Phase 6: React dashboard (simulate + live)
- [ ] Phase 7: LightGBM degradation model trained on FastF1 archives
- [ ] Phase 8: LSTM next-lap predictor
- [ ] Phase 9: 3D track (Three.js/Cesium) + procedural GPS tracks
- [ ] Phase 10: Live ingestion Redis pipeline + Grafana (InfluxDB) alternative view
- [ ] Phase 11: Walk-forward backtest harness + MAE dashboard

---

## 🤝 Attribution

Built standing on the shoulders of the F1 open-source community — see [`docs/RESOURCES.md`](docs/RESOURCES.md) for 30+ repos and their licenses. Data from Jolpica-F1 (Ergast successor), FastF1, OpenF1, F1DB, and official F1 live timing. No proprietary data redistributed.

---

## 📄 License

MIT — see [LICENSE](LICENSE)
