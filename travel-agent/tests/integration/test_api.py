from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def client() -> TestClient:
    app = create_app(Settings(app_env="test", _env_file=None))
    return TestClient(app)


def test_health() -> None:
    with client() as test_client:
        response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "travel-agent"}
    assert response.headers["x-request-id"]


def test_ready_does_not_require_java() -> None:
    with client() as test_client:
        response = test_client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_agent_run_executes_graph() -> None:
    with client() as test_client:
        response = test_client.post(
            "/api/v1/agent/run",
            headers={"x-request-id": "req-api", "x-conversation-id": "conv-header"},
            json={"prompt": "platform check", "conversation_id": "conv-body"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "req-api"
    assert payload["conversation_id"] == "conv-body"
    assert payload["output"] == "Fake model response: platform check"

