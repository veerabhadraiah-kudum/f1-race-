#!/usr/bin/env python3
"""
Fetch real F1 data — demonstrates resource gathering via all APIs.
Usage:
  python scripts/fetch_data.py --year 2024
  python scripts/fetch_data.py --year 2024 --round 6 --fetch-fastf1
"""
import argparse
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--round", type=int, default=None)
    parser.add_argument("--fetch-fastf1", action="store_true", help="Also fetch FastF1 telemetry (slower)")
    args = parser.parse_args()

    from backend.app.services.unified import fetch_session_bundle
    from backend.app.services.jolpica_client import jolpica
    from backend.app.services.openf1_client import openf1

    print(f"Fetching F1 data for {args.year}...")
    # Jolpica schedule
    try:
        print("\n[Jolpica] Schedule...")
        sched = await jolpica.get_schedule(args.year)
        races = sched.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        print(f"  → {len(races)} races")
        for r in races[:5]:
            print(f"    R{r['round']} {r['raceName']} — {r['date']} @ {r['Circuit']['circuitName']}")
        if args.round:
            print(f"\n[Jolpica] Race results R{args.round}...")
            res = await jolpica.get_race_results(args.year, args.round)
            print(f"  → {res}")
    except Exception as e:
        print(f"  Jolpica error: {e}")

    # OpenF1 sessions
    try:
        print(f"\n[OpenF1] Sessions {args.year}...")
        sessions = await openf1.get_sessions(year=args.year)
        print(f"  → {len(sessions)} sessions")
        for s in sessions[:5]:
            print(f"    {s.get('session_name')} @ {s.get('location')} — {s.get('date_start')}")
        if sessions:
            sk = sessions[0].get("session_key")
            if sk:
                print(f"\n[OpenF1] Drivers for session {sk}...")
                drvs = await openf1.get_drivers(int(sk))
                print(f"  → {len(drvs)} drivers")
                for d in drvs[:5]:
                    print(f"    #{d.get('driver_number')} {d.get('full_name')} ({d.get('team_name')})")
    except Exception as e:
        print(f"  OpenF1 error: {e}")

    if args.fetch_fastf1:
        try:
            from backend.app.services.fastf1_service import async_get_schedule
            print(f"\n[FastF1] Schedule {args.year}...")
            sched = await async_get_schedule(args.year)
            print(sched.head().to_string() if hasattr(sched, 'head') else str(sched)[:2000])
        except Exception as e:
            print(f"  FastF1 error: {e}")

    await openf1.close()
    await jolpica.close()
    print("\n✅ Done.")

if __name__ == "__main__":
    asyncio.run(main())
