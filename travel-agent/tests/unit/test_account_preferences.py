import pytest

from app.core.exceptions import AuthenticationError, UpstreamProtocolError
from app.integrations.hmdp.preferences import PreferenceGateway
from app.tools.travel import TravelTools


class Java:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def request_data(self, method, path, kind, **kwargs):
        self.calls.append((method, path, kwargs))
        return self.result


def complete(coroutine):
    # These handlers await only the immediate in-memory Java fake; no event loop is required.
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Unexpected asynchronous IO in unit test")


def test_guest_preferences_require_login_and_never_reach_java():
    java = Java({})
    gateway = PreferenceGateway(java)
    assert complete(gateway.get("guest:abc", None)) == {}
    assert complete(gateway.clear("guest:abc", None)) is None
    with pytest.raises(AuthenticationError):
        complete(gateway.update("guest:abc", None, {"default_city": "南京"}))
    assert java.calls == []
    tools = TravelTools(java, owner="guest:abc", preferences=gateway)
    assert "remember_preferences" not in [t["function"]["name"] for t in tools.schemas()]


def test_java_null_numeric_and_transport_fields_are_unset_preferences():
    gateway = PreferenceGateway(Java({"default_city": "", "budget_per_person": "",
        "transport": "", "cuisines": [], "dietary_notes": []}))
    result = complete(gateway.get("user:123", "opaque"))
    assert "budget_per_person" not in result
    assert "transport" not in result


def test_java_nonempty_invalid_budget_remains_protocol_error():
    gateway = PreferenceGateway(Java({"budget_per_person": "invalid"}))
    with pytest.raises(UpstreamProtocolError):
        complete(gateway.get("user:123", "opaque"))


def test_java_is_authoritative_and_partial_patch_forwards_only_provided_fields():
    java = Java({"budget_per_person": "120.50", "cuisines": []})
    gateway = PreferenceGateway(java)
    saved = complete(gateway.update("user:123", "opaque", {"budget_per_person": 120.5}))
    assert saved["budget_per_person"] == 120.5
    method, path, kwargs = java.calls[0]
    assert (method, path) == ("PATCH", "/user/travel-preferences")
    assert kwargs["json"] == {"budget_per_person": 120.5}
    assert kwargs["auth"].authorization_value == "opaque"
    assert "user_id" not in kwargs["json"]
    java.result = None
    assert complete(gateway.clear("user:123", "opaque")) is None
    with pytest.raises(UpstreamProtocolError):
        complete(gateway.get("user:123", "opaque"))


def test_remember_tool_requires_user_request_and_writes_to_java():
    java = Java({"default_city": "南京"})
    tools = TravelTools(java, "opaque", owner="user:1", preferences=PreferenceGateway(java))
    blocked = complete(tools.execute("remember_preferences", {"default_city": "南京"}))
    assert blocked["error"] == "explicit_request_required"
    assert java.calls == []
    tools.remember_allowed = True
    assert complete(tools.execute("remember_preferences", {"default_city": "南京"}))["saved_preferences"]["default_city"] == "南京"
