"""Read-only local acceptance checks; credentials and response bodies are never printed."""
import argparse
import os
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT))

import httpx
from app.core.config import Settings
from app.memory.factory import create_memory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", default="http://127.0.0.1:8000")
    parser.add_argument("--live-maps", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    failed = 0
    # Explicit bases only; HTTP failures never print URL queries or response contents.
    with httpx.Client(timeout=8, trust_env=False) as client:
        for name, url, key in [
            ("Agent health", args.agent_url + "/health", "status"),
            ("Java categories", str(settings.hmdp_base_url).rstrip("/") + "/shop-type/list", "success"),
        ]:
            try:
                response = client.get(url)
                response.raise_for_status()
                body = response.json()
                if body.get(key) not in (True, "ok"):
                    raise ValueError("Unexpected result")
                print(f"PASS: {name}")
            except Exception as exc:
                failed += 1
                print(f"FAIL: {name} ({type(exc).__name__})")
        token = os.environ.get("TRAVEL_CHECK_TOKEN")
        try:
            response = client.get(args.agent_url + "/api/v1/travel/state",
                                  headers={"authorization": token} if token else {})
            response.raise_for_status()
            state = response.json()
            if token and state.get("guest") is not False:
                raise ValueError("Authenticated identity not confirmed")
            print("PASS: " + ("Authenticated memory/preferences" if token else "Guest memory state"))
            print(("PASS" if state.get("itineraries_ready") else "FAIL") + ": itinerary schema ready")
            failed += not bool(state.get("itineraries_ready"))
            if not token:
                print("SKIP: authenticated preferences (TRAVEL_CHECK_TOKEN not set)")
        except Exception as exc:
            failed += 1
            print(f"FAIL: Agent memory state ({type(exc).__name__})")
        if args.live_maps:
            try:
                response = client.get(args.agent_url + "/api/v1/maps/cities", params={"keyword": "常州"})
                response.raise_for_status()
                assert response.json().get("cities")
                print("PASS: live Amap city lookup")
            except Exception as exc:
                failed += 1
                print(f"FAIL: live Amap lookup ({type(exc).__name__})")
    memory = create_memory(settings)
    try:
        # No initialize() here: checks must not purge expired records or create schema.
        with memory.connection() as db:
            db.execute("SELECT id FROM conversations LIMIT 0")
            db.execute("SELECT id,revision,document FROM itineraries LIMIT 0")
        print(f"PASS: {settings.memory_backend} conversation and itinerary schema")
    except Exception as exc:
        failed += 1
        print(f"FAIL: database check ({type(exc).__name__}); connection and schema are not verified")
    finally:
        memory.close()
    print("Checks complete. SKIP is not verified; model calls and UI interactions are separate checks.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
