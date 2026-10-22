import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import math
from uuid import uuid4

from app.core.exceptions import MapError
from app.integrations.amap import RouteRequest
from app.itineraries.models import CreateItinerary, EditItinerary, ItineraryError, RevisionConflict


def summarize_single(plan):
    """Arithmetic only: route evidence remains distinct from suggested stay times."""
    stops, legs = plan["stops"], plan["legs"]
    known_cost = sum((Decimal(str(s["place"]["cost_yuan"])) for s in stops
                      if s["place"].get("cost_yuan") is not None), Decimal("0")) * plan["people"]
    known_minutes = sum(s["stay_minutes"] for s in stops) + plan["rest_minutes"]
    known_minutes += sum(math.ceil(leg["duration_s"] / 60) for leg in legs if leg.get("duration_s") is not None)
    complete_time = all(leg.get("duration_s") is not None for leg in legs)
    remaining_minutes = sum(s["stay_minutes"] for s in stops if not s["completed"])
    if any(not s["completed"] for s in stops):
        remaining_minutes += plan["rest_minutes"]
    remaining_minutes += sum(math.ceil(leg["duration_s"] / 60) for leg in legs
                             if leg.get("duration_s") is not None and not leg["destination_completed"])
    warnings = ["停留与休息时长为规划建议；营业、预约和门票需出发前确认。",
                "时长只计算行程内安排，不含出发地至首站及返程，请另外预留时间。",
                "费用为高德参考人均的小计，不含交通等未知费用，不能据此保证总预算充足。"]
    if not complete_time:
        warnings.append("部分路线未查到耗时，时间小计不完整；请刷新路线。")
    budget = plan["budget_yuan"]
    over_budget = budget is not None and known_cost > Decimal(str(budget))
    if over_budget:
        warnings.append("仅已知参考费用就已超过总预算，请减少地点或调整预算。")
    window = None
    if plan["start_time"] and plan["end_time"]:
        def minute(value):
            h, m = map(int, value.split(":"))
            return h * 60 + m
        window = minute(plan["end_time"]) - minute(plan["start_time"])
        if known_minutes > window:
            warnings.append("已知安排时长超过可用时间，请删减地点或缩短停留。")
    if len(stops) > 3:
        warnings.append("地点较多，轻松出游建议保留两至三个主要停留点。")
    if not plan["rest_minutes"] and not any(s["kind"] == "rest" for s in stops):
        warnings.append("当前未预留休息时间。")
    return {"known_reference_total_yuan": float(known_cost.quantize(Decimal("0.01"))),
            "known_travel_minutes": sum(math.ceil(leg["duration_s"] / 60) for leg in legs if leg.get("duration_s") is not None),
            "known_distance_m": sum(leg["distance_m"] for leg in legs if leg.get("distance_m") is not None),
            "unknown_price_stops": sum(s["place"].get("cost_yuan") is None for s in stops),
            "budget_status": "over_known" if over_budget else "unconfirmed",
            "known_total_minutes": known_minutes, "remaining_known_minutes": remaining_minutes,
            "time_estimate_complete": complete_time, "available_minutes": window,
            "within_time": (known_minutes <= window if complete_time and window is not None else None),
            "completed_stops": sum(s["completed"] for s in stops), "warnings": warnings}


def summarize(plan):
    """Evaluate each day's window independently; never join overnight route legs."""
    days = []
    for day in range(1, plan.get("day_count", 1) + 1):
        stops = [stop for stop in plan["stops"] if stop.get("day", 1) == day]
        ids = {stop["id"] for stop in stops}
        legs = [leg for leg in plan["legs"] if leg["destination_stop_id"] in ids]
        summary = summarize_single({**plan, "stops": stops, "legs": legs, "budget_yuan": None})
        clock = None
        if plan.get("start_time"):
            hour, minute = map(int, plan["start_time"].split(":"))
            clock = hour * 60 + minute
        schedule = []
        for index, stop in enumerate(stops):
            if index:
                leg = next((leg for leg in legs if leg["destination_stop_id"] == stop["id"]), None)
                clock = (clock + math.ceil(leg["duration_s"] / 60)
                         if clock is not None and leg and leg.get("duration_s") is not None else None)
            def hhmm(value):
                return f"{value // 60:02d}:{value % 60:02d}" if value is not None and value < 1440 else None
            arrival = hhmm(clock)
            rest = plan["rest_minutes"] if index == 0 else 0
            if clock is not None:
                clock += stop["stay_minutes"] + rest
            schedule.append({"stop_id": stop["id"], "arrival_time": arrival,
                             "departure_time": hhmm(clock), "rest_after_minutes": rest})
        travel_date = ((date.fromisoformat(str(plan["start_date"])) + timedelta(days=day - 1)).isoformat()
                       if plan.get("start_date") else None)
        days.append({"day": day, "date": travel_date, "stop_ids": [stop["id"] for stop in stops],
                     "schedule": schedule, **summary})
    if len(days) == 1:
        return {**summarize_single(plan), "days": days}
    costs = sum((Decimal(str(day["known_reference_total_yuan"])) for day in days), Decimal("0"))
    budget = plan.get("budget_yuan")
    over = budget is not None and costs > Decimal(str(budget))
    within = [day["within_time"] for day in days]
    warnings = ["预算为全体同行人的全程总预算；已知参考消费不是完整旅行报价，住宿、交通和门票等仍需核实。",
                "每天独立计算站点间路线，不包含每天首站前的接驳、末站返程或跨城交通。",
                "日程钟点是按查询耗时推算的建议，不等于预约或营业时间；额外休息安排在每天首站之后。"]
    if over:
        warnings.append("仅已知参考费用就已超过全程总预算，请调整安排。")
    for day in days:
        if day["within_time"] is False:
            warnings.append(f"第{day['day']}天已知安排超过当天可用时间，请减少地点或停留。")
        if not day["time_estimate_complete"]:
            warnings.append(f"第{day['day']}天部分路线查询失败，耗时和后续钟点未知，需要刷新路线。")
    return {"days": days, "known_reference_total_yuan": float(costs),
            "known_travel_minutes": sum(day["known_travel_minutes"] for day in days),
            "known_distance_m": sum(day["known_distance_m"] for day in days),
            "unknown_price_stops": sum(day["unknown_price_stops"] for day in days),
            "budget_status": "over_known" if over else "unconfirmed",
            "known_total_minutes": sum(day["known_total_minutes"] for day in days),
            "remaining_known_minutes": sum(day["remaining_known_minutes"] for day in days),
            "time_estimate_complete": all(day["time_estimate_complete"] for day in days),
            "available_minutes": sum(day["available_minutes"] for day in days) if all(day["available_minutes"] is not None for day in days) else None,
            "within_time": False if False in within else True if all(value is True for value in within) else None,
            "completed_stops": sum(day["completed_stops"] for day in days), "warnings": warnings}


class ItineraryService:
    def __init__(self, store, maps):
        self.store, self.maps = store, maps

    async def stop(self, spec, city):
        place = await self.maps.detail(spec.poi_id)
        # Accept city names with/without 市, or a six-digit city/district adcode.
        city_match = str(place.get("city", "")).removesuffix("市") == city.removesuffix("市")
        code_match = (city.isdigit() and len(city) == 6 and
                      str(place.get("adcode", "")).startswith(city[:4] if city.endswith("00") else city))
        if not city_match and not code_match:
            raise ItineraryError("地点不属于所选城市或城市信息缺失，请重新选择准确地点。")
        return {"id": str(uuid4()), "place": place, "stay_minutes": spec.stay_minutes,
                "kind": spec.kind, "day": spec.day, "completed": False}

    async def routes(self, plan, previous=None):
        old = {(leg["origin_stop_id"], leg["destination_stop_id"]): leg for leg in (previous or [])}
        semaphore = asyncio.Semaphore(3)

        async def leg(origin, destination):
            key = (origin["id"], destination["id"])
            # Completed travel remains historical evidence, including after a mode change.
            if destination["completed"] and key in old:
                return old[key]
            async with semaphore:
                try:
                    if hasattr(self.maps, "route_between"):
                        raw = await self.maps.route_between(origin["place"], destination["place"], plan["mode"])
                    else:
                        raw = await self.maps.route(RouteRequest(origin_poi_id=origin["place"]["poi_id"],
                            destination_poi_id=destination["place"]["poi_id"], mode=plan["mode"]))
                    route = {key: raw.get(key) for key in ("duration_s", "distance_m", "computed_at", "navigation_url", "mode", "source")}
                except MapError:
                    route = {"duration_s": None, "distance_m": None, "mode": plan["mode"],
                             "error": "route_unavailable"}
            return {**route, "origin_stop_id": origin["id"], "destination_stop_id": destination["id"],
                    "destination_completed": destination["completed"]}

        pairs = [(a, b) for a, b in zip(plan["stops"], plan["stops"][1:]) if a.get("day", 1) == b.get("day", 1)]
        collected = [None] * len(pairs)
        async def collect(index, origin, destination):
            collected[index] = await leg(origin, destination)
        try:
            async with asyncio.timeout(45):
                await asyncio.gather(*(collect(index, a, b) for index, (a, b) in enumerate(pairs)))
        except TimeoutError:
            # Retain successful route evidence and mark only unfinished segments unknown.
            pass
        plan["legs"] = [item if item is not None else {
            "duration_s": None, "distance_m": None, "mode": plan["mode"], "error": "route_timeout",
            "origin_stop_id": pairs[index][0]["id"], "destination_stop_id": pairs[index][1]["id"],
            "destination_completed": pairs[index][1]["completed"]} for index, item in enumerate(collected)]
        plan["summary"] = summarize(plan)

    async def create(self, owner, payload: CreateItinerary):
        await asyncio.to_thread(self.store.require_ready)
        async with asyncio.timeout(75):
            plan = payload.model_dump(mode="json", exclude={"stops"})
            semaphore = asyncio.Semaphore(3)
            async def fetch(spec):
                async with semaphore:
                    return await self.stop(spec, payload.city)
            plan["stops"] = await asyncio.gather(*(fetch(spec) for spec in payload.stops))
            await self.routes(plan)
        plan["changes"] = [{"action": "created", "at": datetime.now(timezone.utc).isoformat()}]
        return await asyncio.to_thread(self.store.create, owner, plan)

    async def edit(self, owner, itinerary_id, edit: EditItinerary):
        current = await asyncio.to_thread(self.store.get, owner, itinerary_id)
        if current["revision"] != edit.expected_revision:
            raise RevisionConflict("行程已更新，请刷新后再调整。")
        plan = deepcopy(current)
        completed = [s for s in plan["stops"] if s["completed"]]
        index = next((i for i, s in enumerate(plan["stops"]) if s["id"] == str(edit.stop_id)), None)
        if edit.stop_id is not None and index is None:
            raise ItineraryError("此地点不在当前行程中。")
        if index is not None and plan["stops"][index]["completed"]:
            raise ItineraryError("已完成地点已锁定，只能调整后续行程。")
        async with asyncio.timeout(75):
            if edit.action == "complete_stop":
                if index != len(completed):
                    raise ItineraryError("请按行程顺序完成地点，已完成部分将保留。")
                plan["stops"][index]["completed"] = True
                plan["stops"][index]["completed_at"] = datetime.now(timezone.utc).isoformat()
            elif edit.action == "remove_stop":
                if len(plan["stops"]) == 1:
                    raise ItineraryError("行程至少保留一个地点。")
                plan["stops"].pop(index)
            elif edit.action == "move_stop":
                if edit.target_index < len(completed) or edit.target_index >= len(plan["stops"]):
                    raise ItineraryError("只能在尚未完成的地点范围内调整顺序。")
                if plan["stops"][index].get("day", 1) != plan["stops"][edit.target_index].get("day", 1):
                    raise ItineraryError("上移和下移只调整当天顺序，不能跨天移动地点。")
                plan["stops"].insert(edit.target_index, plan["stops"].pop(index))
            elif edit.action == "replace_stop":
                replacement = await self.stop(edit.replacement, plan["city"])
                replacement["id"] = plan["stops"][index]["id"]
                replacement["day"] = plan["stops"][index].get("day", 1)
                plan["stops"][index] = replacement
            elif edit.action == "update_stop":
                for field in ("stay_minutes", "kind"):
                    if field in edit.model_fields_set:
                        plan["stops"][index][field] = getattr(edit, field)
            elif edit.action == "update_plan":
                for field in ("title", "budget_yuan", "mode", "start_time", "end_time", "rest_minutes"):
                    if field in edit.model_fields_set:
                        plan[field] = getattr(edit, field)
            # Validate final constraints after every operation, including repeated POIs/time changes.
            try:
                CreateItinerary.model_validate({**{k: plan[k] for k in CreateItinerary.model_fields if k != "stops" and k in plan},
                    "stops": [{"poi_id": s["place"]["poi_id"], "stay_minutes": s["stay_minutes"], "kind": s["kind"], "day": s.get("day", 1)} for s in plan["stops"]]})
            except ValueError as exc:
                raise ItineraryError("请检查当天重复地点、空白日期、地点数量或时间安排；每天至少保留一站。") from exc
            if plan["stops"][:len(completed)] != completed:
                raise ItineraryError("不能修改已完成的行程片段。")
            if edit.action == "complete_stop":
                for item in plan["legs"]:
                    item["destination_completed"] = next(s for s in plan["stops"] if s["id"] == item["destination_stop_id"])["completed"]
                plan["summary"] = summarize(plan)
            else:
                await self.routes(plan, current["legs"])
        plan["changes"] = [*plan.get("changes", []), {"action": edit.action, "stop_id": str(edit.stop_id) if edit.stop_id else None,
                           "at": datetime.now(timezone.utc).isoformat()}][-30:]
        # Row metadata is authoritative; keep the JSON document free of duplicated versions.
        for key in ("id", "revision", "created_at", "updated_at"):
            plan.pop(key, None)
        return await asyncio.to_thread(self.store.update, owner, itinerary_id, edit.expected_revision, plan)
