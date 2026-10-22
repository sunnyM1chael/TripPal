import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.amap import AmapClient
from app.main import create_app
from tests.unit.test_multiday_itineraries import trip


def test_api_uses_amap_directions_for_each_day_without_duplicate_poi_fetches(tmp_path):
    seen = {"details": 0, "routes": []}
    def amap(request):
        if request.url.path == "/v3/place/detail":
            seen["details"] += 1
            identifier = request.url.params["id"]
            number = int(identifier[-4:])
            return httpx.Response(200, json={"status": "1", "pois": [{"id": identifier, "name": identifier,
                "location": f"119.{number:03d},31.800", "cityname": "常州市", "adcode": "320402", "address": "真实接口形状"}]})
        assert request.url.path == "/v3/direction/walking"
        seen["routes"].append((request.url.params["origin"], request.url.params["destination"]))
        return httpx.Response(200, json={"status": "1", "route": {"paths": [{"distance": "1234", "duration": "900", "steps": []}]}})
    app = create_app(Settings(_env_file=None, memory_db_path=tmp_path / "memory.sqlite3"))
    with TestClient(app) as browser:
        raw = httpx.AsyncClient(base_url="https://restapi.amap.com", transport=httpx.MockTransport(amap))
        app.state.container.itineraries.maps = AmapClient(raw, "test-key")
        try:
            payload = trip(day_count=2, stops=[{"poi_id": f"POI{i:04d}", "day": (i - 1) // 2 + 1} for i in range(1, 5)])
            response = browser.post("/api/v1/itineraries", json=payload.model_dump(mode="json"))
            assert response.status_code == 201
            plan = response.json()
            assert seen["details"] == 4 and len(seen["routes"]) == 2
            assert seen["routes"] == [("119.001000,31.800000", "119.002000,31.800000"), ("119.003000,31.800000", "119.004000,31.800000")]
            assert all(leg["duration_s"] == 900 and leg["distance_m"] == 1234 and leg["source"] == "amap" for leg in plan["legs"])
            restored = browser.get(f'/api/v1/itineraries/{plan["id"]}').json()
            assert restored["summary"]["days"][1]["date"] == "2026-10-31"
        finally:
            browser.portal.call(raw.aclose)
