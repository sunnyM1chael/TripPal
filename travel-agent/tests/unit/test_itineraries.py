from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import MapError, NotFoundError
from app.itineraries.models import CreateItinerary, EditItinerary, ItineraryError, RevisionConflict
from app.itineraries.service import ItineraryService
from app.itineraries.store import ItineraryStore
from app.memory.store import MemoryStore


def test_mysql_schema_recovers_after_external_migration_without_restart(monkeypatch):
    from contextlib import contextmanager
    from app.itineraries.models import ItineraryUnavailable

    class Database:
        installed = False
        checks = 0
        settings = object()

        @contextmanager
        def connection(self):
            yield self

        def execute(self, sql):
            assert sql.startswith("SELECT ")  # runtime must never install tables
            self.checks += 1
            if not self.installed:
                raise Exception(1146, "missing table")

    clock = [0]
    monkeypatch.setattr("app.itineraries.store.time.monotonic", lambda: clock[0])
    db = Database()
    store = ItineraryStore(db)
    store.initialize()
    with pytest.raises(ItineraryUnavailable, match="app.memory.admin init"):
        store.require_ready()
    checks = db.checks
    assert not store.check_ready()
    assert db.checks == checks
    db.installed = True
    clock[0] = 6
    store.require_ready()
    assert store.ready
    assert db.checks == checks + 1


class Maps:
    def __init__(self):
        self.calls = []
        self.fail_route = False

    async def detail(self, poi_id):
        return {"poi_id": poi_id, "name": "地点" + poi_id, "city": "常州市", "adcode": "320402",
                "address": "已查询地址", "location": "119.97,31.81", "source": "amap",
                "cost_yuan": 80 if poi_id == "POI0001" else None}

    async def route(self, request):
        self.calls.append(request)
        if self.fail_route:
            raise MapError("offline")
        return {"duration_s": 600, "distance_m": 700, "computed_at": "2026-10-21T01:00:00Z",
                "mode": request.mode, "navigation_url": "https://uri.amap.com/navigation?mode=walk"}


@pytest.fixture
def service(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    memory.initialize()
    store = ItineraryStore(memory)
    store.initialize()
    return ItineraryService(store, Maps())


def payload(**kwargs):
    return CreateItinerary(title="常州轻松游", city="常州", people=2, budget_yuan=100,
        start_time="14:00", end_time="15:00", stops=[{"poi_id": "POI0001"}, {"poi_id": "POI0002"}], **kwargs)


async def test_saved_plan_survives_restart_and_checks_real_constraints(service):
    plan = await service.create("guest:a", payload())
    restarted = ItineraryStore(MemoryStore(service.store.memory.path))
    restarted.initialize()
    assert restarted.get("guest:a", plan["id"]) == plan
    assert plan["summary"]["known_reference_total_yuan"] == 160
    assert plan["summary"]["budget_status"] == "over_known"
    assert plan["summary"]["unknown_price_stops"] == 1
    assert plan["summary"]["known_total_minutes"] == 150
    assert plan["summary"]["within_time"] is False
    assert restarted.list("guest:b") == []
    with pytest.raises(NotFoundError):
        restarted.get("guest:b", plan["id"])


async def test_completed_prefix_is_immutable_and_remaining_replacement_refreshes_route(service):
    plan = await service.create("user:a", payload())
    first, second = plan["stops"]
    plan = await service.edit("user:a", plan["id"], EditItinerary(expected_revision=1,
        action="complete_stop", stop_id=first["id"]))
    frozen = deepcopy(plan["stops"][0])
    for action in ["remove_stop", "complete_stop", "replace_stop", "move_stop", "update_stop"]:
        args = {"expected_revision": 2, "action": action, "stop_id": first["id"]}
        if action == "replace_stop": args["replacement"] = {"poi_id": "POI0003"}
        if action == "move_stop": args["target_index"] = 1
        if action == "update_stop": args["stay_minutes"] = 10
        with pytest.raises(ItineraryError):
            await service.edit("user:a", plan["id"], EditItinerary(**args))
    plan = await service.edit("user:a", plan["id"], EditItinerary(expected_revision=2,
        action="replace_stop", stop_id=second["id"], replacement={"poi_id": "POI0003", "stay_minutes": 30}))
    assert plan["revision"] == 3
    assert plan["stops"][0] == frozen
    assert plan["stops"][1]["place"]["poi_id"] == "POI0003"
    assert service.maps.calls[-1].destination_poi_id == "POI0003"


async def test_stale_revision_cannot_overwrite_or_delete(service):
    plan = await service.create("user:a", payload())
    await service.edit("user:a", plan["id"], EditItinerary(expected_revision=1, action="refresh_routes"))
    with pytest.raises(RevisionConflict):
        await service.edit("user:a", plan["id"], EditItinerary(expected_revision=1, action="refresh_routes"))
    with pytest.raises(RevisionConflict):
        service.store.delete("user:a", plan["id"], 1)
    assert service.store.get("user:a", plan["id"])["revision"] == 2


async def test_simultaneous_writes_only_one_wins(service):
    plan = await service.create("user:a", payload())
    def update():
        try:
            service.store.update("user:a", plan["id"], 1, {"title": plan["title"], "marker": str(uuid4())})
            return "saved"
        except RevisionConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: update(), range(2))) == ["conflict", "saved"]


async def test_foreign_owner_cannot_mutate(service):
    plan = await service.create("user:a", payload())
    with pytest.raises(NotFoundError):
        await service.edit("user:b", plan["id"], EditItinerary(expected_revision=1, action="refresh_routes"))
    with pytest.raises(NotFoundError):
        service.store.delete("user:b", plan["id"], 1)


async def test_route_failure_stays_unknown_and_does_not_claim_schedule_fits(service):
    service.maps.fail_route = True
    plan = await service.create("user:a", payload())
    assert plan["legs"][0]["duration_s"] is None
    assert plan["summary"]["within_time"] is None
    assert plan["summary"]["time_estimate_complete"] is False


async def test_invalid_move_duplicate_replacement_and_completion_order_leave_revision_unchanged(service):
    plan = await service.create("user:a", payload())
    with pytest.raises(ItineraryError):
        await service.edit("user:a", plan["id"], EditItinerary(expected_revision=1, action="complete_stop", stop_id=plan["stops"][1]["id"]))
    with pytest.raises(ItineraryError):
        await service.edit("user:a", plan["id"], EditItinerary(expected_revision=1, action="replace_stop",
            stop_id=plan["stops"][1]["id"], replacement={"poi_id": "POI0001"}))
    assert service.store.get("user:a", plan["id"])["revision"] == 1


async def test_wrong_city_is_rejected_before_persistence(service):
    bad = payload().model_copy(update={"city": "南京"})
    with pytest.raises(ItineraryError):
        await service.create("user:a", bad)
    assert service.store.list("user:a") == []


async def test_delete_and_forget_are_owner_scoped(service):
    a = await service.create("user:a", payload())
    b = await service.create("user:b", payload())
    service.store.delete("user:a", a["id"], 1)
    assert service.store.list("user:a") == []
    service.store.forget("user:a")
    assert service.store.get("user:b", b["id"])["id"] == b["id"]


@pytest.mark.parametrize("data", [
    {"expected_revision": 1, "action": "remove_stop"},
    {"expected_revision": 1, "action": "refresh_routes", "title": "hidden change"},
    {"expected_revision": 1, "action": "update_plan", "mode": None},
    {"expected_revision": 1, "action": "update_plan", "budget_yuan": float("nan")},
])
def test_invalid_edit_payloads_are_rejected(data):
    with pytest.raises(ValidationError):
        EditItinerary.model_validate(data)


async def test_agent_tools_save_once_and_read_latest_revision(service):
    from app.tools.travel import TravelTools
    tools = TravelTools(None, itineraries=service, owner="user:a")
    args = payload().model_dump()
    created = (await tools.execute("create_itinerary", args))["itinerary"]
    read = (await tools.execute("get_current_itinerary", {}))["itinerary"]
    assert read["id"] == created["id"]
    result = (await tools.execute("edit_current_itinerary", {"action": "remove_stop", "expected_revision": 1,
                                                            "stop_id": read["stops"][1]["id"]}))["itinerary"]
    assert result["revision"] == 2
    repeated = (await tools.execute("create_itinerary", args))["itinerary"]
    assert repeated["revision"] == 2
    assert len(service.store.list("user:a")) == 1


async def test_agent_must_select_an_owned_itinerary_before_adjusting(service):
    from app.tools.travel import TravelTools
    tools = TravelTools(None, itineraries=service, owner="user:a")
    with pytest.raises(ItineraryError):
        await tools.execute("get_current_itinerary", {})
    assert "create_itinerary" in [tool["function"]["name"] for tool in tools.schemas()]
    # MCP builds TravelTools without an itinerary service, so no writes are advertised.
    assert "create_itinerary" not in [tool["function"]["name"] for tool in TravelTools(None).schemas()]


async def test_completed_route_evidence_is_retained_when_remaining_mode_changes(service):
    raw = payload().model_dump()
    raw["stops"].append({"poi_id": "POI0003"})
    plan = await service.create("user:a", CreateItinerary.model_validate(raw))
    for index in range(2):
        plan = await service.edit("user:a", plan["id"], EditItinerary(expected_revision=index + 1,
            action="complete_stop", stop_id=plan["stops"][index]["id"]))
    historical_leg = deepcopy(plan["legs"][0])
    calls_before = len(service.maps.calls)
    plan = await service.edit("user:a", plan["id"], EditItinerary(expected_revision=3,
        action="update_plan", mode="driving"))
    assert plan["legs"][0] == historical_leg
    assert plan["legs"][1]["mode"] == "driving"
    assert len(service.maps.calls) == calls_before + 1
    assert plan["summary"]["remaining_known_minutes"] == 90


async def test_chat_tool_loop_creates_reads_and_edits_the_same_saved_plan(service):
    import json
    from app.domain.models import ChatMessage, ToolCall, ToolFunction
    from app.services.travel import TravelRequest, run_travel
    from app.tools.travel import TravelTools

    class Model:
        calls = 0
        async def ainvoke(self, messages, *, tools):
            self.calls += 1
            if self.calls == 1:
                name, arguments = "create_itinerary", payload().model_dump()
            elif self.calls == 2:
                name, arguments = "get_current_itinerary", {}
            elif self.calls == 3:
                latest = json.loads(messages[-1].content)["itinerary"]
                name, arguments = "edit_current_itinerary", {"action": "remove_stop", "expected_revision": latest["revision"],
                                                           "stop_id": latest["stops"][1]["id"]}
            else:
                return ChatMessage(role="assistant", content="已保存并调整行程。")
            return ChatMessage(role="assistant", content="", tool_calls=[ToolCall(id=f"trip-{self.calls}",
                function=ToolFunction(name=name, arguments=json.dumps(arguments)))])

    response = await run_travel(Model(), TravelTools(None, itineraries=service, owner="user:a"),
                               TravelRequest(prompt="常州两人轻松游，总预算100元，然后删掉第二站"))
    latest = response.tool_results[-1]["data"]["itinerary"]
    assert latest["revision"] == 2 and len(latest["stops"]) == 1
    assert service.store.get("user:a", latest["id"])["revision"] == 2
    assert len(service.store.list("user:a")) == 1
