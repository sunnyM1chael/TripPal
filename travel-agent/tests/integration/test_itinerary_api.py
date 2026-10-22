from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.unit.test_itineraries import Maps, payload


def test_guest_itinerary_create_edit_restore_and_owner_isolation(tmp_path):
    app = create_app(Settings(_env_file=None, memory_db_path=tmp_path / "memory.sqlite3"))
    with TestClient(app) as first, TestClient(app) as other:
        app.state.container.itineraries.maps = Maps()
        response = first.post("/api/v1/itineraries", json=payload().model_dump())
        assert response.status_code == 201
        plan = response.json()
        path = f'/api/v1/itineraries/{plan["id"]}'
        assert first.get(path).json()["revision"] == 1
        assert other.get(path).status_code == 404
        assert other.patch(path, json={"action": "refresh_routes", "expected_revision": 1}).status_code == 404
        changed = first.patch(path, json={"action": "remove_stop", "expected_revision": 1, "stop_id": plan["stops"][1]["id"]})
        assert changed.status_code == 200
        assert len(changed.json()["stops"]) == 1
        assert first.patch(path, json={"action": "refresh_routes", "expected_revision": 1}).status_code == 409
        assert first.delete(path, params={"expected_revision": 1}).status_code == 409
        assert first.get("/api/v1/itineraries").json()["itineraries"][0]["revision"] == 2
        assert first.delete(path, params={"expected_revision": 2}).status_code == 200
        assert first.get(path).status_code == 404


def test_payload_cannot_forge_a_place_snapshot_or_owner(tmp_path):
    app = create_app(Settings(_env_file=None, memory_db_path=tmp_path / "memory.sqlite3"))
    with TestClient(app) as client:
        body = payload().model_dump()
        body["owner"] = "user:victim"
        assert client.post("/api/v1/itineraries", json=body).status_code == 422
        body.pop("owner")
        body["stops"][0]["place"] = {"name": "fabricated", "cost_yuan": 0}
        assert client.post("/api/v1/itineraries", json=body).status_code == 422


def test_forget_also_clears_saved_itineraries(tmp_path):
    app = create_app(Settings(_env_file=None, memory_db_path=tmp_path / "memory.sqlite3"))
    with TestClient(app) as client:
        app.state.container.itineraries.maps = Maps()
        assert client.post("/api/v1/itineraries", json=payload().model_dump()).status_code == 201
        assert client.delete("/api/v1/travel/memory").status_code == 200
        assert client.get("/api/v1/itineraries").json()["itineraries"] == []
