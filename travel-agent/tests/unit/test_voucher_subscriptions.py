import json
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.core.exceptions import AuthenticationError, NotFoundError
from app.integrations.hmdp.client import HmdpClient
from app.services.voucher_subscription import (
    ConfirmSubscription, PrepareSubscription, SubscriptionError, SubscriptionRequest, VoucherSubscriptions,
)
from app.tools.travel import TravelTools


class JavaSubscriptions:
    def __init__(self):
        self.state = 0
        self.writes = []
        self.fail_write = False
        self.fail_readback = False
        self.rule = "限堂食"
        self.voucher_type = "1"
        self.end = (datetime.now(timezone(timedelta(hours=8))) + timedelta(days=1)).replace(tzinfo=None).isoformat()

    def __call__(self, request):
        assert request.headers["authorization"] == "private-token"
        path = request.url.path
        if path == "/shop/11":
            data = {"id": "11", "name": "小店", "avgPrice": "80"}
        elif path == "/shop/of/name":
            data = [{"id": "11", "name": "小店", "avgPrice": "80"}]
        elif path == "/voucher/list/11":
            data = [{"id": "21", "shopId": "11", "title": "双人券", "payValue": "9900", "actualValue": "12000",
                     "type": self.voucher_type, "status": "1", "beginTime": "2026-01-01 00:00:00", "endTime": self.end, "rules": self.rule}]
        elif path == "/voucher/get/subscribe/status":
            if self.fail_readback and self.writes:
                raise httpx.ReadTimeout("readback failed")
            data = str(self.state)  # actual Java long/integer serialization
        elif path in {"/voucher/subscribe", "/voucher/unsubscribe"}:
            assert json.loads(request.content) == {"voucherId": 21}
            self.writes.append(path)
            self.state = 1 if path.endswith("/subscribe") else 0
            if self.fail_write:
                raise httpx.ReadTimeout("write may already be applied")
            data = None
        elif path == "/user/me":
            data = {"id": "7"}
        elif path == "/user/travel-preferences":
            data = {}
        else:
            pytest.fail(f"Unexpected Java request {path}")
        return httpx.Response(200, json={"success": True, "data": data, "total": "", "errorMsg": ""})


@pytest.fixture
async def setup():
    java = JavaSubscriptions()
    async with httpx.AsyncClient(base_url="http://java", transport=httpx.MockTransport(java)) as raw:
        client = HmdpClient(raw, timeout=1, max_attempts=3)
        yield java, VoucherSubscriptions(client), client


def request(action="subscribe"):
    return PrepareSubscription(shop_id=11, voucher_id=21, action=action)


async def test_prepare_does_not_write_then_confirm_readback_and_cancel(setup):
    java, service, _ = setup
    card = await service.prepare("user:7", "private-token", request())
    assert card["phase"] == "awaiting_confirmation" and java.writes == []
    with pytest.raises(SubscriptionError):
        await service.confirm("user:7", "private-token", card["action_id"], ConfirmSubscription(confirmed=True))
    assert java.writes == []
    receipt = await service.confirm("user:7", "private-token", card["action_id"], ConfirmSubscription(confirmed=True, accept_auto_issue=True))
    assert receipt["verified"] and receipt["target_reached"] and receipt["status"] == 1
    cancel = await service.prepare("user:7", "private-token", request("unsubscribe"))
    assert java.writes == ["/voucher/subscribe"]
    result = await service.confirm("user:7", "private-token", cancel["action_id"], ConfirmSubscription(confirmed=True))
    assert result["status"] == 0 and result["target_reached"]
    replay = await service.confirm("user:7", "private-token", card["action_id"], ConfirmSubscription(confirmed=True, accept_auto_issue=True))
    assert replay["status"] == 0 and replay["replayed"] and not replay["target_reached"]
    assert java.writes == ["/voucher/subscribe", "/voucher/unsubscribe"]


async def test_guest_and_other_owner_cannot_execute_or_observe_card(setup):
    java, service, _ = setup
    with pytest.raises(AuthenticationError):
        await service.prepare("guest:a", None, request())
    card = await service.prepare("user:7", "private-token", request())
    with pytest.raises(NotFoundError):
        await service.confirm("user:8", "private-token", card["action_id"], ConfirmSubscription(confirmed=True, accept_auto_issue=True))
    assert not java.writes


async def test_expired_or_changed_terms_require_new_card(setup):
    java, service, _ = setup
    card = await service.prepare("user:7", "private-token", request())
    service.pending[card["action_id"]].expires_at = 0
    with pytest.raises(SubscriptionError, match="过期"):
        await service.confirm("user:7", "private-token", card["action_id"], ConfirmSubscription(confirmed=True, accept_auto_issue=True))
    card = await service.prepare("user:7", "private-token", request())
    java.rule = "新增使用限制"
    with pytest.raises(SubscriptionError, match="变化"):
        await service.confirm("user:7", "private-token", card["action_id"], ConfirmSubscription(confirmed=True, accept_auto_issue=True))
    assert not java.writes


async def test_timeouts_are_read_back_and_never_retried_as_writes(setup):
    java, service, _ = setup
    java.fail_write = True
    card = await service.prepare("user:7", "private-token", request())
    receipt = await service.confirm("user:7", "private-token", card["action_id"], ConfirmSubscription(confirmed=True, accept_auto_issue=True))
    assert receipt["write_outcome_uncertain"] and receipt["verified"] and receipt["status"] == 1
    assert len(java.writes) == 1
    await service.confirm("user:7", "private-token", card["action_id"], ConfirmSubscription(confirmed=True, accept_auto_issue=True))
    assert len(java.writes) == 1


async def test_unconfirmed_result_never_claims_success(setup):
    java, service, _ = setup
    card = await service.prepare("user:7", "private-token", request())
    java.fail_readback = True
    receipt = await service.confirm("user:7", "private-token", card["action_id"], ConfirmSubscription(confirmed=True, accept_auto_issue=True))
    assert receipt["phase"] == "unverified" and receipt["verified"] is False
    assert "status" not in receipt and "target_reached" not in receipt
    assert len(java.writes) == 1


async def test_already_issued_cannot_be_cancelled_as_a_subscription(setup):
    java, service, _ = setup
    java.state = 2
    card = await service.prepare("user:7", "private-token", request("unsubscribe"))
    receipt = await service.confirm("user:7", "private-token", card["action_id"], ConfirmSubscription(confirmed=True))
    assert receipt["status"] == 2 and not receipt["target_reached"] and not java.writes


async def test_normal_expired_and_wrong_shop_vouchers_are_rejected(setup):
    java, service, _ = setup
    java.voucher_type = "0"
    with pytest.raises(SubscriptionError):
        await service.prepare("user:7", "private-token", request())
    java.voucher_type = "1"
    java.end = "2020-01-01 00:00:00"
    with pytest.raises(SubscriptionError):
        await service.prepare("user:7", "private-token", request())
    with pytest.raises(NotFoundError):
        await service.status("user:7", "private-token", SubscriptionRequest(shop_id=11, voucher_id=999))
    assert not java.writes


async def test_model_can_only_prepare_and_query_never_confirm(setup):
    java, service, client = setup
    tools = TravelTools(client, "private-token", owner="user:7", subscriptions=service)
    names = {row["function"]["name"] for row in tools.schemas()}
    assert {"prepare_voucher_subscription", "get_voucher_subscription"} <= names
    assert "confirm_voucher_subscription" not in names
    assert (await tools.execute("confirm_voucher_subscription", {}))["error"] == "unknown_tool"
    result = await tools.execute("prepare_voucher_subscription", request().model_dump())
    assert result["subscription_action"]["phase"] == "awaiting_confirmation" and not java.writes
    assert "private-token" not in json.dumps(result)
    vouchers = await tools.execute("shop_vouchers", {"shop_id": 11})
    assert vouchers["vouchers"][0]["pay_yuan"] == 99
    assert vouchers["vouchers"][0]["type"] == "1"
    guest = TravelTools(client, subscriptions=service, owner="guest:a")
    assert "prepare_voucher_subscription" not in {row["function"]["name"] for row in guest.schemas()}


async def test_concurrent_confirmation_only_writes_once_and_restart_expires_card(setup):
    java, service, client = setup
    card = await service.prepare("user:7", "private-token", request())
    confirmation = ConfirmSubscription(confirmed=True, accept_auto_issue=True)
    receipts = await asyncio.gather(*(service.confirm("user:7", "private-token", card["action_id"], confirmation) for _ in range(3)))
    assert all(result["verified"] and result["status"] == 1 for result in receipts)
    assert java.writes == ["/voucher/subscribe"]
    restarted = VoucherSubscriptions(client)
    assert (await restarted.status("user:7", "private-token", request()))["status"] == 1
    with pytest.raises(NotFoundError):
        await restarted.confirm("user:7", "private-token", card["action_id"], confirmation)


async def test_real_java_string_prices_can_be_filtered_before_voucher_action(setup):
    _, _, client = setup
    tools = TravelTools(client, "private-token")
    result = await tools.execute("search_shops", {"name": "小店", "max_price": 100})
    assert len(result["shops"]) == 1 and result["shops"][0]["avgPrice"] == 80
    assert (await tools.execute("search_shops", {"name": "小店", "max_price": 50}))["shops"] == []
