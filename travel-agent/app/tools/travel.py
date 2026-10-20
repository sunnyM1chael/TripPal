"""Read-only business tools. All paths and argument schemas are server-owned."""
import asyncio

from pydantic import BaseModel, ConfigDict, Field

from app.integrations.hmdp.client import HmdpClient
from app.integrations.hmdp.models import AuthContext
from app.integrations.amap import AmapClient, RouteRequest
from app.memory.models import Preferences
from app.memory.store import MemoryStore


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


class CitySearch(Arguments):
    keyword: str = Field(min_length=1, max_length=40)


class PlaceSearch(Arguments):
    city: str = Field(min_length=1, max_length=40)
    keyword: str = Field(min_length=1, max_length=100)
    page: int = Field(default=1, ge=1, le=20)


MAP_DEFINITIONS = {
    "search_cities": (CitySearch, "查询城市/区县名称与adcode；同名结果请让用户选择。"),
    "search_city_places": (PlaceSearch, "在明确指定的城市内搜索真实高德地点（餐饮/景点/车站等）。返回高德poi_id，不能作为平台shop_id查询优惠券。"),
    "plan_route": (RouteRequest, "通过搜索得到的两个高德poi_id查询驾车或步行路线、耗时和导航入口。不猜坐标或地点ID。"),
}


DEFINITIONS = {
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
    shop["score"] = raw["score"] / 10 if isinstance(raw.get("score"), (int, float)) else None
    shop["price_unit"] = "CNY/person"
    return shop


class TravelTools:
    def __init__(self, client: HmdpClient, authorization: str | None = None, *, maps: AmapClient | None = None,
                 memory: MemoryStore | None = None, preferences=None, owner: str | None = None, remember_allowed: bool = False):
        self.client = client
        self.auth = AuthContext(authorization_value=authorization)
        self.maps, self.memory, self.owner = maps, memory, owner
        self.remember_allowed = remember_allowed
        self.preferences = preferences
        self.authorization = authorization

    def schemas(self):
        definitions = {**DEFINITIONS}
        if self.maps:
            definitions.update(MAP_DEFINITIONS)
        if self.preferences and self.owner and self.owner.startswith("user:"):
            definitions["remember_preferences"] = (Preferences, "仅在用户本轮明确要求记住偏好时调用，保存结构化出行偏好。未提及的字段不要填写，禁止从商户数据推断用户偏好。")
        return [{"type": "function", "function": {"name": name, "description": description,
                 "parameters": schema.model_json_schema()}} for name, (schema, description) in definitions.items()]

    async def get(self, path: str, kind: type, params: dict | None = None):
        return await self.client.request_data("GET", path, kind, params=params, auth=self.auth)

    async def execute(self, name: str, arguments: dict) -> dict:
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
            keys = ("id", "shopId", "title", "subTitle", "rules", "status", "stock", "beginTime", "endTime")
            vouchers = []
            for row in rows:
                voucher = {key: row.get(key) for key in keys}
                # SQL schema defines voucher monetary fields in cents, unlike Shop.avgPrice.
                voucher["pay_yuan"] = row["payValue"] / 100 if row.get("payValue") is not None else None
                voucher["value_yuan"] = row["actualValue"] / 100 if row.get("actualValue") is not None else None
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
