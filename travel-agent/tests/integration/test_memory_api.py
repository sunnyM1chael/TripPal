import hashlib
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.hmdp.client import HmdpClient
from app.integrations.hmdp.preferences import PreferenceGateway
from app.main import create_app


def test_logged_in_state_accepts_actual_java_null_serialization(tmp_path):
    app = create_app(Settings(_env_file=None, memory_db_path=tmp_path / "memory.sqlite3"))

    def java(request):
        assert request.headers["authorization"] == "opaque-token"
        data = ({"id": "9007199254740993", "nickName": "traveler"}
                if request.url.path == "/user/me" else {
                    "default_city": "", "budget_per_person": "", "transport": "",
                    "cuisines": [], "dietary_notes": []})
        return httpx.Response(200, json={"success": True, "errorMsg": "", "total": "", "data": data})

    with TestClient(app) as client:
        raw = httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(java))
        app.state.container.hmdp_client = HmdpClient(raw, timeout=1)
        app.state.container.preferences = PreferenceGateway(app.state.container.hmdp_client)
        try:
            response = client.get("/api/v1/travel/state", headers={"authorization": "opaque-token"})
            assert response.status_code == 200
            assert response.json()["guest"] is False
            assert "budget_per_person" not in response.json()["preferences"]
        finally:
            client.portal.call(raw.aclose)


def test_guest_cookie_keeps_history_but_cannot_save_account_preferences(tmp_path):
    settings = Settings(_env_file=None, app_env="test", memory_db_path=tmp_path / "test.sqlite3")
    first_app, second_app = create_app(settings), create_app(settings)
    with TestClient(first_app) as first, TestClient(second_app) as second:
        assert first.get("/api/v1/travel/state").json()["guest"] is True
        cookie = first.cookies.get("travel_visitor")
        assert cookie
        owner = "guest:" + hashlib.sha256(cookie.encode()).hexdigest()
        saved = first.put("/api/v1/travel/preferences", json={"default_city": "南京", "budget_per_person": 100})
        assert saved.status_code == 401
        assert first.get("/api/v1/travel/state").json()["preferences"] == {}
        assert second.get("/api/v1/travel/state").json()["preferences"] == {}
        assert first.get("/api/v1/travel/state", headers={"x-user-id": "victim"}).json()["preferences"] == {}
        conv, lease = first_app.state.container.memory.begin(owner, None, "test")
        first_app.state.container.memory.finish(owner, conv, lease, "test", SimpleNamespace(output="result", mode="live", stopped=False, tool_results=[]))
        assert first.get(f"/api/v1/travel/conversations/{conv}").status_code == 200
        assert second.get(f"/api/v1/travel/conversations/{conv}").status_code == 404
        assert second.delete(f"/api/v1/travel/conversations/{conv}").status_code == 404
        assert first.delete("/api/v1/travel/memory").status_code == 200
        assert first.get("/api/v1/travel/state").json()["preferences"] == {}


def test_invalid_authorization_never_falls_back_to_guest(tmp_path):
    app = create_app(Settings(_env_file=None, memory_db_path=tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        raw = httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(lambda request: httpx.Response(401)))
        app.state.container.hmdp_client = HmdpClient(raw, timeout=1, max_attempts=1)
        assert client.get("/api/v1/travel/state", headers={"authorization": "invalid"}).status_code == 401


def test_map_configuration_is_explicit(tmp_path):
    app = create_app(Settings(_env_file=None, memory_db_path=tmp_path / "test.sqlite3", amap_api_key=None))
    with TestClient(app) as client:
        assert client.get("/api/v1/maps/status").json()["configured"] is False
        response = client.get("/api/v1/maps/places", params={"city": "南京", "keyword": "火锅"})
        assert response.status_code == 503
        assert response.json()["code"] == "map_not_configured"
