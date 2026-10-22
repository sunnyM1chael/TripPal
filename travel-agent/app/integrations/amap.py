import math
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import MapError, MapNotConfiguredError


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)

    def coordinate(self):
        return f"{self.longitude:.6f},{self.latitude:.6f}"


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin_poi_id: str = Field(pattern=r"^[A-Za-z0-9_-]{5,40}$")
    destination_poi_id: str = Field(pattern=r"^[A-Za-z0-9_-]{5,40}$")
    mode: Literal["driving", "walking"] = "driving"


def parse_point(value) -> Point | None:
    if not isinstance(value, str):
        return None
    try:
        longitude, latitude = value.split(",")
        return Point(longitude=float(longitude), latitude=float(latitude))
    except (ValueError, TypeError):
        return None


def navigation_url(destination: dict, origin: dict | None = None, mode: str = "driving") -> str:
    params = {"to": f"{destination['location']},{str(destination['name']).replace(',', ' ')}",
              "mode": "walk" if mode == "walking" else "car", "src": "TripPal", "callnative": "1"}
    if origin:
        params["from"] = f"{origin['location']},{str(origin['name']).replace(',', ' ')}"
    return "https://uri.amap.com/navigation?" + urlencode(params)


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError):
        return None


class AmapClient:
    def __init__(self, client: httpx.AsyncClient, key: str | None, timeout: float = 8):
        self.client, self.key, self.timeout = client, key, timeout

    @property
    def configured(self):
        return bool(self.key)

    async def request(self, path: str, params: dict) -> dict:
        if not self.key:
            raise MapNotConfiguredError("地图服务尚未配置，请设置服务端 AMAP_API_KEY（高德 Web 服务 Key）。")
        try:
            response = await self.client.get(path, params={**params, "key": self.key}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or str(data.get("status")) != "1":
                raise MapError("地图查询未成功，请检查地图服务权限与配额。")
            return data
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise MapError("地图服务暂时不可用，请稍后重试。") from exc

    async def cities(self, keyword: str) -> dict:
        data = await self.request("/v3/config/district", {"keywords": keyword, "subdistrict": 1, "extensions": "base", "offset": 20})
        cities = {}
        for district in data.get("districts", []):
            rows = [district, *district.get("districts", [])]
            for row in rows:
                if row.get("level") not in {"province", "city", "district"}:
                    continue
                point = parse_point(row.get("center"))
                if point:
                    cities[row["adcode"]] = {"name": row["name"], "adcode": row["adcode"], "level": row["level"], "location": point.coordinate()}
        return {"cities": list(cities.values())[:30], "source": "amap"}

    @staticmethod
    def place(row: dict) -> dict | None:
        point = parse_point(row.get("location"))
        if not point or not isinstance(row.get("id"), str):
            return None
        business = row.get("biz_ext") or {}
        if not isinstance(business, dict):
            business = {}
        result = {"poi_id": row["id"], "name": row.get("name", ""), "address": row.get("address") if isinstance(row.get("address"), str) else "",
                  "city": row.get("cityname") if isinstance(row.get("cityname"), str) else "", "district": row.get("adname"),
                  "adcode": row.get("adcode"), "location": point.coordinate(), "source": "amap",
                  "rating": number(business.get("rating")), "cost_yuan": number(business.get("cost"))}
        result["navigation_url"] = navigation_url(result)
        return result

    async def search(self, city: str, keyword: str, page: int = 1) -> dict:
        data = await self.request("/v3/place/text", {"city": city, "citylimit": "true", "keywords": keyword,
                                                   "offset": 10, "page": page, "extensions": "all"})
        places = [place for row in data.get("pois", []) if (place := self.place(row))]
        return {"places": places, "city": city, "page": page, "source": "amap",
                "notice": "高德地点，不等于平台已入驻商户；不提供平台优惠券承诺，均价仅供参考。"}

    async def detail(self, poi_id: str) -> dict:
        data = await self.request("/v3/place/detail", {"id": poi_id, "extensions": "all"})
        rows = data.get("pois", [])
        place = self.place(rows[0]) if rows else None
        if not place:
            raise MapError("未找到具有有效坐标的地点，请重新选择。")
        return place

    async def route(self, payload: RouteRequest) -> dict:
        origin = await self.detail(payload.origin_poi_id)
        destination = await self.detail(payload.destination_poi_id)
        return await self.route_between(origin, destination, payload.mode)

    async def route_between(self, origin: dict, destination: dict, mode: str) -> dict:
        """Internal fast path for POIs already fetched and validated by this service."""
        params = {"origin": origin["location"], "destination": destination["location"]}
        if mode == "driving":
            path = "/v5/direction/driving"
            params.update({"strategy": 32, "show_fields": "cost,polyline,tmcs"})
        else:
            path = "/v3/direction/walking"
        data = await self.request(path, params)
        paths = data.get("route", {}).get("paths", [])
        if not paths:
            raise MapError("这两个地点之间未查到可用路线，请调整出行方式。")
        route = paths[0]
        steps = [{"instruction": str(step.get("instruction", ""))[:300], "distance_m": number(step.get("distance")),
                  "road": step.get("road") if isinstance(step.get("road"), str) else ""} for step in route.get("steps", [])[:100]]
        coordinates = []
        for step in route.get("steps", []):
            for value in str(step.get("polyline", "")).split(";"):
                point = parse_point(value)
                if point:
                    coordinates.append(point.coordinate())
        # Bounded route preview. Use the native navigation link for full live guidance.
        stride = max(1, math.ceil(len(coordinates) / 80))
        preview_points = coordinates[::stride]
        if coordinates and preview_points[-1] != coordinates[-1]:
            preview_points.append(coordinates[-1])
        preview_params = {"origin": origin["location"], "destination": destination["location"], "path": ";".join(preview_points)}
        return {"origin": origin, "destination": destination, "mode": mode,
                "distance_m": number(route.get("distance")),
                "duration_s": number((route.get("cost") or {}).get("duration") or route.get("duration")),
                "steps": steps, "source": "amap", "computed_at": datetime.now(timezone.utc).isoformat(),
                "navigation_url": navigation_url(destination, origin, mode),
                "preview_url": "/agent-api/api/v1/maps/preview?" + urlencode(preview_params),
                "notice": "路线与耗时为本次查询结果，出发前可刷新。持续定位、语音与实时重算由高德导航提供。"}

    async def preview(self, origin: str, destination: str, path: str) -> bytes:
        points = [parse_point(item) for item in path.split(";") if item]
        if len(points) > 81 or any(point is None for point in points):
            raise MapError("路线预览坐标无效。")
        start, end = parse_point(origin), parse_point(destination)
        if not start or not end:
            raise MapError("起终点坐标无效。")
        if not self.key:
            raise MapNotConfiguredError("地图服务尚未配置。")
        params = {"key": self.key, "size": "600*320", "scale": 2, "traffic": 1,
                  "markers": f"mid,0x3D9F83,A:{start.coordinate()}|mid,0xE87850,B:{end.coordinate()}"}
        if points:
            params["paths"] = "4,0xE87850,1,,:" + ";".join(p.coordinate() for p in points)
        try:
            response = await self.client.get("/v3/staticmap", params=params, timeout=self.timeout)
            response.raise_for_status()
            if not response.headers.get("content-type", "").startswith("image/") or len(response.content) > 4_000_000:
                raise MapError("地图预览不可用，可直接打开高德导航。")
            return response.content
        except httpx.HTTPError as exc:
            raise MapError("地图预览暂时不可用。") from exc
