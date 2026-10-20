import httpx
import pytest

from app.core.exceptions import MapError, MapNotConfiguredError
from app.integrations.amap import AmapClient, RouteRequest


async def test_city_limited_search_and_no_secret_in_result():
    def handler(request):
        assert request.url.path == "/v3/place/text"
        assert request.url.params["city"] == "320100"
        assert request.url.params["citylimit"] == "true"
        assert request.url.params["key"] == "test-private-key"
        return httpx.Response(200, json={"status": "1", "pois": [{"id": "B12345", "name": "火锅店", "location": "118.8,32.1", "cityname": "南京市"}]})
    async with httpx.AsyncClient(base_url="https://restapi.amap.com", transport=httpx.MockTransport(handler)) as raw:
        result = await AmapClient(raw, "test-private-key").search("320100", "火锅")
    assert result["places"][0]["city"] == "南京市"
    assert "test-private-key" not in str(result)


async def test_route_uses_poi_coordinates_and_returns_real_duration():
    seen = []
    def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/v3/place/detail":
            point = "118.8,32.1" if request.url.params["id"] == "BSTART" else "118.9,32.2"
            return httpx.Response(200, json={"status": "1", "pois": [{"id": request.url.params["id"], "name": "地点", "location": point}]})
        assert request.url.path == "/v5/direction/driving"
        assert request.url.params["origin"] == "118.800000,32.100000"
        assert request.url.params["strategy"] == "32"
        return httpx.Response(200, json={"status": "1", "route": {"paths": [{"distance": "5000", "cost": {"duration": "900"}, "steps": [{"instruction": "沿道路直行", "distance": "5000", "polyline": "118.8,32.1;118.9,32.2"}]}]}})
    async with httpx.AsyncClient(base_url="https://restapi.amap.com", transport=httpx.MockTransport(handler)) as raw:
        result = await AmapClient(raw, "secret").route(RouteRequest(origin_poi_id="BSTART", destination_poi_id="BDESTI"))
    assert result["distance_m"] == 5000 and result["duration_s"] == 900
    assert result["navigation_url"].startswith("https://uri.amap.com/navigation?")
    assert result["preview_url"].startswith("/agent-api/api/v1/maps/preview?")
    assert len(seen) == 3


async def test_missing_key_does_not_send_network_request():
    def handler(request):
        pytest.fail("No API key must not trigger any network call")
    async with httpx.AsyncClient(base_url="https://restapi.amap.com", transport=httpx.MockTransport(handler)) as raw:
        with pytest.raises(MapNotConfiguredError):
            await AmapClient(raw, None).cities("南京")


async def test_provider_error_is_redacted():
    async with httpx.AsyncClient(base_url="https://restapi.amap.com", transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "0", "info": "private-key-leak"}))) as raw:
        with pytest.raises(MapError) as captured:
            await AmapClient(raw, "secret").cities("南京")
    assert "private-key-leak" not in captured.value.message
