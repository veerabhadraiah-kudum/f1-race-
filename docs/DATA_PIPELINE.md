# Data Pipeline — Real-Time F1 Ingestion

## Sources & Update Frequency

| Source | Latency | Coverage | Key Endpoints |
|---|---|---|---|
| **Jolpica-F1** | ~hours post-race | 1950→Now | /{year}, /{year}/{round}/results, /standings |
| **FastF1** | 20-120min post-session | 2018→Now | Timing, telemetry, weather, race control |
| **OpenF1** | 3s real-time | 2023→Now | /laps, /car_data, /location, /intervals, /weather |
| **F1 LiveTiming (SignalR)** | <1s | Live only | Official timing screens (decoded via matteocelani/f1-telemetry) |

## Unified Schema

All feeds fold into `RaceState` (Pydantic) via `backend/app/services/unified.py`:

```
RaceState = { session_key, session_name, circuit, flag, lap, total_laps, elapsed, cars[], race_control[], weather, timestamp }
CarState  = { driver_number, position, gap, interval, last_lap, compound, tyre_age, pit_stops, speed, throttle, brake, gear, drs, x, y, status }
```

## Ingestion Flow

```
Poll OpenF1 (3s) → delta-merge (reducer.py) → Redis pub/sub → FastAPI WS @10Hz → Frontend 60fps rAF
          ↑
     Jolpica (schedule) + FastF1 (telemetry) enrich on session start
```

- **Delta merge** is safety-critical — see `Ark07Yad/pitwall: state/merge.py`. We only emit deltas.
- **Caching:** FastF1 file cache (`./data/cache`), Jolpica 24h, OpenF1 5s in-memory.
- **Fallback:** If upstream fails (429/5xx), serve `MOCK_SESSION` + cached.

## Rate Limiting

- Jolpica: generous, no auth
- OpenF1: 3 req/s, 30/min — we pace at 2.5 req/s via token bucket
- FastF1: 4 req/s burst, 500/hr — mitigated by caching

## Replay Mode

For offline demo or post-race analysis: backend streams archived telemetry at 1×–64× via same WS. Frontend interpolates via `requestAnimationFrame + lerp`.

## Monitoring

- `/api/health` → source statuses
- Logs: ingest latency, dropped deltas, WS fan-out p99
