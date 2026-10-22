"""Business queries and preparation tools; subscription writes require the UI."""
import asyncio
import math
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field

from app.integrations.hmdp.client import HmdpClient
from app.integrations.hmdp.models import AuthContext
from app.integrations.amap import AmapClient, RouteRequest
from app.memory.models import Preferences
from app.memory.store import MemoryStore
from app.core.exceptions import AppError
from app.services.voucher_subscription import PrepareSubscription, SubscriptionRequest


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArguments(Arguments):
    pass


class Search(Arguments):
    name: str = Field(min_length=1, max_length=100)
    page: int = Field(default=1, ge=1, le=20)
    max_price: float | None = Field(default=None, ge=0)


class Category(Arguments):
    type_id: int = Field(gt=0)
    page: int = Field(default=1, ge=1, le=20)
    max_price: float | None = Field(default=None, ge=0)


class ShopId(Arguments):
    shop_id: int = Field(gt=0)


class DayPlan(Arguments):
    shop_ids: list[int] = Field(min_length=1, max_length=6)
    people: int = Field(default=1, ge=1, le=20)
    budget: float | None = Field(default=None, ge=0)


class CompareShops(Arguments):
    shop_ids: list[int] = Field(min_length=2, max_length=4)
    budget_per_person: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class CitySearch(Arguments):
    keyword: str = Field(min_length=1, max_length=40)


class PlaceSearch(Arguments):
    city: str = Field(min_length=1, max_length=40)
    keyword: str = Field(min_length=1, max_length=100)
    page: int = Field(default=1, ge=1, le=20)


class TripPlaceSearch(Arguments):
    city: str = Field(min_length=1, max_length=40)
    keywords: list[str] = Field(min_length=1, max_length=6, description="按用户兴趣生成的地点或同城区域关键词；每项1至60字")


MAP_DEFINITIONS = {
    "search_cities": (CitySearch, "查询城市/区县名称与adcode；同名结果请让用户选择。"),
    "search_city_places": (PlaceSearch, "在明确指定的城市内搜索真实高德地点（餐饮/景点/车站等）。返回高德poi_id，不能作为平台shop_id查询优惠券。"),
    "plan_route": (RouteRequest, "通过搜索得到的两个高德poi_id查询驾车或步行路线、耗时和导航入口。不猜坐标或地点ID。"),
}


DEFINITIONS = {
    "compare_shops": (CompareShops, "并行核查2至4家真实平台商户的价格、评分、营业时间与优惠券，返回对比依据与未知项，不做全城排名。"),
    "list_categories": (NoArguments, "查询真实商户分类和分类ID，按分类搜索前先调用。"),
    "search_shops": (Search, "按店名关键词分页搜索；不是城市或地址搜索。max_price筛选当前页已知人均价格。"),
    "shops_by_category": (Category, "按真实分类ID分页查询商户，可筛选当前页人均预算；不代表附近或全城排名。"),
    "shop_detail": (ShopId, "查询商户真实详情、人均价格、评分、地址和营业时间。"),
    "shop_vouchers": (ShopId, "查询商户优惠券与规则；不下单、不承诺库存或可购买状态。"),
    "plan_day": (DayPlan, "按用户选择的商户ID顺序构建一日探店草案，并计算多人预计消费。不是地图导航或预约。"),
}


def tool_schemas() -> list[dict]:
    return [{"type": "function", "function": {"name": name, "description": description,
            "parameters": schema.model_json_schema()}}
            for name, (schema, description) in DEFINITIONS.items()]


def shop_view(raw: dict) -> dict:
    # Shop.java stores score multiplied by ten; avgPrice is integer yuan.
    keys = ("id", "name", "typeId", "area", "address", "avgPrice", "openHours", "x", "y")
    shop = {key: raw.get(key) for key in keys}
    for key in ("avgPrice", "score"):
        try:
            value = float(raw.get(key))
            shop[key] = value if math.isfinite(value) and value >= 0 else None
        except (TypeError, ValueError):
            shop[key] = None
    if shop["score"] is not None:
        shop["score"] /= 10
    shop["price_unit"] = "CNY/person"
    return shop


def voucher_yuan(value):
    # Java serializes Long values as decimal strings; missing money stays unknown.
    try:
        amount = Decimal(str(value))
        return float(amount / 100) if amount.is_finite() and amount >= 0 else None
    except InvalidOperation:
        return None


class TravelTools:
    def __init__(self, client: HmdpClient, authorization: str | None = None, *, maps: AmapClient | None = None,
                 memory: MemoryStore | None = None, preferences=None, owner: str | None = None, remember_allowed: bool = False,
                 itineraries=None, itinerary_id: str | None = None, subscriptions=None):
        self.client = client
        self.auth = AuthContext(authorization_value=authorization)
        self.maps, self.memory, self.owner = maps, memory, owner
        self.remember_allowed = remember_allowed
        self.preferences = preferences
        self.authorization = authorization
        self.itineraries, self.itinerary_id = itineraries, itinerary_id
        self.created_itinerary = None
        self.subscriptions = subscriptions

    def schemas(self):
        definitions = {**DEFINITIONS}
        if self.subscriptions and self.owner and self.owner.startswith("user:"):
            definitions.update({
                "prepare_voucher_subscription": (PrepareSubscription, "查询真实券并准备候补订阅或取消操作卡；尚未执行。用户必须在页面核对并点击确认，模型不能代为确认。订阅可能自动发券创建券订单。"),
                "get_voucher_subscription": (SubscriptionRequest, "回查当前登录账号在 Java 系统的优惠券候补状态；不订阅、不取消。"),
            })
        if self.itineraries and self.itineraries.store.ready and self.owner:
            from app.itineraries.tools import DEFINITIONS as itinerary_definitions
            definitions.update(itinerary_definitions)
        if self.maps:
            definitions.update(MAP_DEFINITIONS)
            definitions["search_trip_places"] = (TripPlaceSearch, "为多日行程批量搜索同城真实高德候选，每个关键词最多5处、并发最多3个查询；不能编造poi_id。失败项标为未知。")
        if self.preferences and self.owner and self.owner.startswith("user:"):
            definitions["remember_preferences"] = (Preferences, "仅在用户本轮明确要求记住偏好时调用，保存结构化出行偏好。未提及的字段不要填写，禁止从商户数据推断用户偏好。")
        return [{"type": "function", "function": {"name": name, "description": description,
                 "parameters": schema.model_json_schema()}} for name, (schema, description) in definitions.items()]

    async def get(self, path: str, kind: type, params: dict | None = None):
        return await self.client.request_data("GET", path, kind, params=params, auth=self.auth)

    async def execute(self, name: str, arguments: dict) -> dict:
        if name == "search_trip_places" and self.maps:
            args = TripPlaceSearch.model_validate(arguments)
            if not args.city.strip() or any(not value.strip() or len(value) > 60 for value in args.keywords):
                raise ValueError("城市和地点关键词不能为空，关键词最多60字")
            semaphore = asyncio.Semaphore(3)
            async def search(keyword):
                async with semaphore:
                    try:
                        data = await self.maps.search(args.city.strip(), keyword.strip(), 1)
                        return {"keyword": keyword, "places": data.get("places", [])[:5], "source": "amap"}
                    except AppError as exc:
                        return {"keyword": keyword, "places": [], "error": exc.code, "message": exc.message}
            return {"city": args.city, "groups": await asyncio.gather(*(search(keyword) for keyword in dict.fromkeys(args.keywords))),
                    "notice": "先按地址和区域分天，再用create_itinerary核验地点和实际路线。没有结果的关键词不代表该城没有此类地点。"}
        if self.subscriptions and self.owner and self.owner.startswith("user:"):
            if name == "prepare_voucher_subscription":
                args = PrepareSubscription.model_validate(arguments)
                return {"subscription_action": await self.subscriptions.prepare(self.owner, self.authorization, args)}
            if name == "get_voucher_subscription":
                args = SubscriptionRequest.model_validate(arguments)
                return {"subscription_status": await self.subscriptions.status(self.owner, self.authorization, args)}
        if self.itineraries and self.owner:
            from app.itineraries.tools import DEFINITIONS as itinerary_definitions
            if name in itinerary_definitions:
                from app.itineraries.models import ItineraryError
                args = itinerary_definitions[name][0].model_validate(arguments)
                if name == "create_itinerary":
                    if self.created_itinerary is None:
                        self.created_itinerary = await self.itineraries.create(self.owner, args)
                        self.itinerary_id = self.created_itinerary["id"]
                    return {"itinerary": await asyncio.to_thread(self.itineraries.store.get, self.owner, self.created_itinerary["id"])}
                if not self.itinerary_id:
                    raise ItineraryError("请先在我的行程中打开一份行程，再提出调整要求。")
                if name == "get_visit_feedback":
                    plan = await asyncio.to_thread(self.itineraries.store.get, self.owner, self.itinerary_id)
                    return {"itinerary_id": plan["id"], "visits": [
                        {"stop_id": stop["id"], "place_name": stop["place"]["name"], "feedback": stop["feedback"]}
                        for stop in plan["stops"] if stop["completed"] and stop.get("feedback")],
                        "notice": "用户自述，仅用于本人回顾；不是验证到店记录，也不代表长期偏好或平台评分。"}
                if name == "get_current_itinerary":
                    return {"itinerary": await asyncio.to_thread(self.itineraries.store.get, self.owner, self.itinerary_id)}
                return {"itinerary": await self.itineraries.edit(self.owner, self.itinerary_id, args)}
        if name in MAP_DEFINITIONS and self.maps:
            args = MAP_DEFINITIONS[name][0].model_validate(arguments)
            if name == "search_cities":
                return await self.maps.cities(args.keyword)
            if name == "search_city_places":
                return await self.maps.search(args.city, args.keyword, args.page)
            return await self.maps.route(args)
        if name == "remember_preferences" and self.preferences and self.owner and self.owner.startswith("user:"):
            if not self.remember_allowed:
                return {"error": "explicit_request_required", "message": "请用户明确说“记住我的偏好”后再保存。"}
            args = Preferences.model_validate(arguments)
            preferences = await self.preferences.update(self.owner, self.authorization, args.model_dump(exclude_unset=True))
            return {"saved_preferences": preferences, "notice": "已保存，可在我的记忆中修改或删除。"}
        if name not in DEFINITIONS:
            return {"error": "unknown_tool", "message": "只能调用已公布的工具。"}
        args = DEFINITIONS[name][0].model_validate(arguments)
        if name == "compare_shops":
            async def compare(shop_id):
                detail, vouchers = await asyncio.gather(
                    self.execute("shop_detail", {"shop_id": shop_id}),
                    self.execute("shop_vouchers", {"shop_id": shop_id}))
                shop = detail["shop"]
                price = shop.get("avgPrice") if shop else None
                return {"shop_id": shop_id, "shop": shop, "vouchers": vouchers["vouchers"],
                        "within_budget": price <= args.budget_per_person if price is not None and args.budget_per_person is not None else None,
                        "unknown_fields": [key for key in ("avgPrice", "score", "openHours") if not shop or shop.get(key) is None]}
            return {"comparisons": await asyncio.gather(*(compare(i) for i in dict.fromkeys(args.shop_ids))),
                    "notice": "仅比较所选商户；券不能默认叠加，价格与营业信息需出发前复核。"}
        if name == "list_categories":
            rows = await self.get("/shop-type/list", list[dict]) or []
            return {"categories": [{"id": row.get("id"), "name": row.get("name")} for row in rows]}
        if name in {"search_shops", "shops_by_category"}:
            path = "/shop/of/name" if name == "search_shops" else "/shop/of/type"
            params = {"current": args.page}
            params.update({"name": args.name} if name == "search_shops" else {"typeId": args.type_id})
            rows = await self.get(path, list[dict], params) or []
            shops = [shop_view(row) for row in rows]
            if args.max_price is not None:
                shops = [s for s in shops if s["avgPrice"] is not None and s["avgPrice"] <= args.max_price]
            return {"shops": shops, "page": args.page, "scope": "当前页；未知价格不参与预算筛选", "source": path}
        if name == "shop_detail":
            row = await self.get(f"/shop/{args.shop_id}", dict)
            return {"shop": shop_view(row) if row else None}
        if name == "shop_vouchers":
            rows = await self.get(f"/voucher/list/{args.shop_id}", list[dict]) or []
            keys = ("id", "shopId", "title", "subTitle", "rules", "type", "status", "stock", "beginTime", "endTime")
            vouchers = []
            for row in rows:
                voucher = {key: row.get(key) for key in keys}
                # SQL schema defines voucher monetary fields in cents, unlike Shop.avgPrice.
                voucher["pay_yuan"] = voucher_yuan(row.get("payValue"))
                voucher["value_yuan"] = voucher_yuan(row.get("actualValue"))
                vouchers.append(voucher)
            return {"vouchers": vouchers, "currency": "CNY",
                    "notice": "状态、库存与有效期需以购买页实时校验为准。"}
        stops = []
        for shop_id in dict.fromkeys(args.shop_ids):
            if shop_id <= 0:
                return {"error": "invalid_shop_id"}
            row = await self.get(f"/shop/{shop_id}", dict)
            if not row:
                return {"error": "shop_not_found", "shop_id": shop_id}
            stops.append(shop_view(row))
        known = sum(s["avgPrice"] for s in stops if s["avgPrice"] is not None) * args.people
        complete = all(s["avgPrice"] is not None for s in stops)
        return {"stops": stops, "people": args.people, "known_estimate_yuan": known,
                "estimate_complete": complete, "budget_yuan": args.budget,
                "within_budget": known <= args.budget if complete and args.budget is not None else None,
                "notice": "按输入顺序探店草案；均价仅估算，不含交通住宿。不验证实时营业、路程或预约。"}
