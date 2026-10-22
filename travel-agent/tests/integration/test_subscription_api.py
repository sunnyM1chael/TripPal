import json

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.models import ChatMessage, ToolCall, ToolFunction
from app.integrations.hmdp.client import HmdpClient
from app.integrations.hmdp.preferences import PreferenceGateway
from app.main import create_app
from app.services.voucher_subscription import VoucherSubscriptions
from tests.unit.test_voucher_subscriptions import JavaSubscriptions


class SubscriptionModel:
    def __init__(self):
        self.step = 0

    async def ainvoke(self, messages, *, tools):
        calls = [("search_shops", {"name": "小店"}), ("shop_vouchers", {"shop_id": 11}),
                 ("prepare_voucher_subscription", {"shop_id": 11, "voucher_id": 21, "action": "subscribe"})]
        if self.step >= len(calls):
            return ChatMessage(role="assistant", content="已准备候补卡，请核对规则并在卡片中确认；尚未订阅。")
        name, arguments = calls[self.step]
        self.step += 1
        return ChatMessage(role="assistant", content="", tool_calls=[ToolCall(id=str(self.step),
            function=ToolFunction(name=name, arguments=json.dumps(arguments)))])


def test_chat_prepare_ui_confirm_java_readback_and_cancel(tmp_path):
    app = create_app(Settings(_env_file=None, memory_db_path=tmp_path / "memory.sqlite3"))
    java = JavaSubscriptions()
    with TestClient(app) as browser:
        raw = httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(java))
        container = app.state.container
        container.hmdp_client = HmdpClient(raw, timeout=1)
        container.preferences = PreferenceGateway(container.hmdp_client)
        container.subscriptions = VoucherSubscriptions(container.hmdp_client)
        container.settings.llm_provider = "scripted"
        container.llm = SubscriptionModel()
        try:
            assert browser.post("/api/v1/voucher-subscriptions/prepare", json={"shop_id": 11, "voucher_id": 21}).status_code == 401
            browser.headers["authorization"] = "private-token"
            response = browser.post("/api/v1/travel/chat", json={"prompt": "帮我查小店的券，准备候补订阅"})
            assert response.status_code == 200
            body = response.json()
            card = body["tool_results"][-1]["data"]["subscription_action"]
            assert not java.writes
            path = f'/api/v1/voucher-subscriptions/{card["action_id"]}/confirm'
            assert browser.post(path, json={"confirmed": True}).status_code == 409
            assert browser.post(path, json={"confirmed": True, "accept_auto_issue": True, "owner": "user:8"}).status_code == 422
            receipt = browser.post(path, json={"confirmed": True, "accept_auto_issue": True})
            assert receipt.status_code == 200 and receipt.json()["status"] == 1
            assert browser.post(path, json={"confirmed": True, "accept_auto_issue": True}).json()["replayed"]
            status = browser.get("/api/v1/voucher-subscriptions/status", params={"shop_id": 11, "voucher_id": 21})
            assert status.json()["verified"] and status.json()["status"] == 1
            assert browser.get("/api/v1/voucher-subscriptions/status", params={"shop_id": -1, "voucher_id": 21}).status_code == 422
            card = browser.post("/api/v1/voucher-subscriptions/prepare", json={"shop_id": 11, "voucher_id": 21, "action": "unsubscribe"}).json()
            receipt = browser.post(f'/api/v1/voucher-subscriptions/{card["action_id"]}/confirm', json={"confirmed": True})
            assert receipt.json()["status"] == 0 and receipt.json()["target_reached"]
            assert java.writes == ["/voucher/subscribe", "/voucher/unsubscribe"]
            assert "private-token" not in json.dumps(body)
        finally:
            browser.portal.call(raw.aclose)
