import asyncio
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from app.core.exceptions import MapError
from app.domain.models import ChatMessage, ToolCall, ToolFunction
from app.itineraries.models import CreateItinerary, EditItinerary, ItineraryError
from app.itineraries.service import ItineraryService
from app.itineraries.store import ItineraryStore
from app.memory.store import MemoryStore
from app.services.travel import TravelRequest, run_travel
from app.tools.travel import TravelTools
from tests.unit.test_itineraries import Maps


def trip(**changes):
    data = {"title": "常州三天慢游", "city": "常州", "people": 2, "budget_yuan": 100,
            "day_count": 3, "start_date": "2026-10-30", "start_time": "09:00", "end_time": "12:00",
            "mode": "walking", "rest_minutes": 20, "preferences": ["园林", "少赶路"],
            "stops": [{"poi_id": f"POI{i:04d}", "day": (i - 1) // 2 + 1} for i in range(1, 7)]}
    return CreateItinerary.model_validate({**data, **changes})


@pytest.fixture
def service(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    memory.initialize()
    store = ItineraryStore(memory)
    store.initialize()
    return ItineraryService(store, Maps())


async def test_each_day_routes_dates_budget_and_schedule_are_independent(service):
    plan = await service.create("user:a", trip())
    assert len(service.maps.calls) == 3
    assert [(call.origin_poi_id, call.destination_poi_id) for call in service.maps.calls] == [
        ("POI0001", "POI0002"), ("POI0003", "POI0004"), ("POI0005", "POI0006")]
    days = plan["summary"]["days"]
    assert [day["date"] for day in days] == ["2026-10-30", "2026-10-31", "2026-11-01"]
    assert all(day["known_total_minutes"] == 150 and day["within_time"] for day in days)
    assert days[0]["schedule"][0]["arrival_time"] == "09:00"
    assert days[0]["schedule"][1]["arrival_time"] == "10:30"
    assert plan["summary"]["known_total_minutes"] == 450
    assert plan["summary"]["known_reference_total_yuan"] == 160
    assert plan["summary"]["budget_status"] == "over_known"
    assert plan["summary"]["unknown_price_stops"] == 5
    assert plan["preferences"] == ["园林", "少赶路"]
    assert service.store.get("user:a", plan["id"])["start_date"] == "2026-10-30"


async def test_one_day_overflow_is_not_hidden_by_another_days_spare_time(service):
    stops = [{"poi_id": f"POI{i:04d}", "day": (i - 1) // 2 + 1, "stay_minutes": 100 if i <= 2 else 5}
             for i in range(1, 5)]
    plan = await service.create("user:a", trip(day_count=2, stops=stops))
    assert plan["summary"]["known_total_minutes"] < plan["summary"]["available_minutes"]
    assert plan["summary"]["within_time"] is False
    assert plan["summary"]["days"][0]["within_time"] is False
    assert plan["summary"]["days"][1]["within_time"] is True


async def test_missing_route_does_not_invent_clocks_or_affect_another_day(service):
    original = service.maps.route
    async def route(request):
        if request.origin_poi_id == "POI0001":
            raise MapError("not available")
        return await original(request)
    service.maps.route = route
    plan = await service.create("user:a", trip())
    first, second = plan["summary"]["days"][:2]
    assert first["time_estimate_complete"] is False
    assert first["schedule"][1]["arrival_time"] is None
    assert first["schedule"][1]["departure_time"] is None
    assert second["time_estimate_complete"] and second["schedule"][0]["arrival_time"] == "09:00"
    assert plan["legs"][0]["duration_s"] is None


async def test_route_deadline_preserves_finished_segments_and_marks_pending_unknown(service, monkeypatch):
    original_route = service.maps.route
    original_timeout = asyncio.timeout
    async def slow_route(request):
        if request.origin_poi_id != "POI0001":
            await asyncio.sleep(1)
        return await original_route(request)
    service.maps.route = slow_route
    monkeypatch.setattr("app.itineraries.service.asyncio.timeout", lambda seconds: original_timeout(0.005 if seconds == 45 else seconds))
    plan = await service.create("user:a", trip())
    assert plan["legs"][0]["duration_s"] == 600
    assert all(leg["duration_s"] is None and leg["error"] == "route_timeout" for leg in plan["legs"][1:])
    assert plan["summary"]["days"][0]["time_estimate_complete"] is True
    assert plan["summary"]["time_estimate_complete"] is False


@pytest.mark.parametrize("start_date", ["9999-12-31", "not-a-date"])
def test_invalid_or_overflowing_trip_dates_are_rejected(start_date):
    with pytest.raises(ValidationError):
        trip(start_date=start_date)


async def test_edits_keep_day_assignment_and_reject_cross_day_or_empty_days(service):
    plan = await service.create("user:a", trip())
    first_on_day_two = plan["stops"][2]
    with pytest.raises(ItineraryError, match="跨天"):
        await service.edit("user:a", plan["id"], EditItinerary(action="move_stop", expected_revision=1,
            stop_id=first_on_day_two["id"], target_index=1))
    plan = await service.edit("user:a", plan["id"], EditItinerary(action="replace_stop", expected_revision=1,
        stop_id=first_on_day_two["id"], replacement={"poi_id": "POI0099"}))
    assert plan["stops"][2]["day"] == 2
    plan = await service.edit("user:a", plan["id"], EditItinerary(action="remove_stop", expected_revision=2,
        stop_id=plan["stops"][3]["id"]))
    with pytest.raises(ItineraryError):
        await service.edit("user:a", plan["id"], EditItinerary(action="remove_stop", expected_revision=3,
            stop_id=plan["stops"][2]["id"]))
    assert service.store.get("user:a", plan["id"])["revision"] == 3


async def test_legacy_single_day_document_can_still_be_edited(service):
    from tests.unit.test_itineraries import payload
    plan = await service.create("user:a", payload())
    legacy = deepcopy(plan)
    for key in ("id", "revision", "created_at", "updated_at", "day_count", "start_date", "preferences"):
        legacy.pop(key, None)
    for stop in legacy["stops"]:
        stop.pop("day", None)
    legacy["summary"].pop("days", None)
    service.store.update("user:a", plan["id"], 1, legacy)
    changed = await service.edit("user:a", plan["id"], EditItinerary(action="update_stop", expected_revision=2,
        stop_id=plan["stops"][0]["id"], stay_minutes=45))
    assert len(changed["summary"]["days"]) == 1 and changed["stops"][0]["stay_minutes"] == 45


@pytest.mark.parametrize("changes", [
    {"day_count": 8}, {"day_count": 0}, {"day_count": 4},
    {"stops": [{"poi_id": "POI0001", "day": 1}, {"poi_id": "POI0001", "day": 1}]},
    {"stops": [{"poi_id": f"POI{i:04d}", "day": 1} for i in range(1, 6)] + [{"poi_id": "POI0006", "day": 2}, {"poi_id": "POI0007", "day": 3}]},
    {"stops": [{"poi_id": "POI0001", "day": 2}, {"poi_id": "POI0002", "day": 1}, {"poi_id": "POI0003", "day": 3}]},
    {"preferences": ["x" * 61]}, {"end_time": "08:00"},
])
def test_invalid_day_assignments_and_constraints_are_rejected(changes):
    with pytest.raises(ValidationError):
        trip(**changes)


async def test_batch_candidates_are_bounded_and_partial_failures_visible():
    class SearchMaps:
        active = 0
        peak = 0
        async def search(self, city, keyword, page):
            self.active += 1
            self.peak = max(self.peak, self.active)
            await asyncio.sleep(0)
            self.active -= 1
            if keyword == "失败":
                raise MapError("查询失败")
            return {"places": [{"poi_id": f"POI{i:04d}"} for i in range(10)]}
    maps = SearchMaps()
    tools = TravelTools(None, maps=maps)
    data = await tools.execute("search_trip_places", {"city": "常州", "keywords": ["园林", "公园", "失败", "博物馆"]})
    assert maps.peak <= 3
    assert len(data["groups"][0]["places"]) == 5
    assert data["groups"][2]["error"] == "map_unavailable"


async def test_skill_tool_loop_saves_a_multiday_plan_with_real_route_calls(service):
    async def search(city, keyword, page):
        return {"places": [await service.maps.detail(f"POI{i:04d}") for i in range(1, 7)]}
    service.maps.search = search
    class Model:
        step = 0
        async def ainvoke(self, messages, *, tools):
            self.step += 1
            if self.step == 1:
                name, args = "search_trip_places", {"city": "常州", "keywords": ["园林"]}
            elif self.step == 2:
                candidates = json.loads(messages[-1].content)["groups"][0]["places"]
                assert candidates[0]["poi_id"] == "POI0001"
                data = trip(day_count=2, stops=[{"poi_id": row["poi_id"], "day": index // 2 + 1} for index, row in enumerate(candidates[:4])])
                name, args = "create_itinerary", data.model_dump(mode="json")
            else:
                return ChatMessage(role="assistant", content="已按两天保存，路线由高德查询；费用仍有未知项。")
            return ChatMessage(role="assistant", content="", tool_calls=[ToolCall(id=f"day-{self.step}",
                function=ToolFunction(name=name, arguments=json.dumps(args)))])
    result = await run_travel(Model(), TravelTools(None, owner="user:a", itineraries=service, maps=service.maps),
        TravelRequest(prompt="常州两天两个人总预算100元，园林慢游，生成并保存", skill="plan-city-trip"))
    assert result.loaded_skills == ["plan-city-trip"]
    saved = result.tool_results[-1]["data"]["itinerary"]
    assert saved["day_count"] == 2 and len(saved["summary"]["days"]) == 2
    assert len(service.maps.calls) == 2 and len(service.store.list("user:a")) == 1
