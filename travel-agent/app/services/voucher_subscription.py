"""Prepare -> explicit UI confirmation -> Java write -> read-back.

Pending confirmations are bounded, short-lived process state, never authority supplied
by the model. Java remains the source of subscription truth. Restart expires cards.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import time
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import AppError, AuthenticationError, IntegrationError, NotFoundError
from app.integrations.hmdp.models import AuthContext


class SubscriptionError(AppError):
    code = "operation_invalid"
    status_code = 409


class SubscriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shop_id: int = Field(gt=0, le=9223372036854775807)
    voucher_id: int = Field(gt=0, le=9223372036854775807)


class PrepareSubscription(SubscriptionRequest):
    action: Literal["subscribe", "unsubscribe"] = "subscribe"


class ConfirmSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: Literal[True]
    accept_auto_issue: bool = False


LABELS = {0: "未订阅候补", 1: "候补队列中", 2: "已发券并创建订单"}
NOTICE = "这会加入 Java 系统的优惠券候补队列。补库存或退券时可能自动发券并创建券订单；不是普通提醒，不承诺一定获得优惠券。"


@dataclass
class PendingSubscription:
    owner: str
    request: PrepareSubscription
    snapshot: dict
    digest: str
    expires_at: float
    attempted: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class VoucherSubscriptions:
    def __init__(self, client):
        self.client = client
        self.pending = {}

    @staticmethod
    def authenticate(owner, authorization):
        if not owner.startswith("user:") or not authorization:
            raise AuthenticationError("请先登录，再查看或操作优惠券候补。")

    async def _request(self, method, path, kind, authorization, body=None):
        return await self.client.request_data(method, path, kind,
            auth=AuthContext(authorization_value=authorization), json=body, retry=False)

    async def snapshot(self, owner, authorization, request):
        self.authenticate(owner, authorization)
        shop = await self._request("GET", f"/shop/{request.shop_id}", dict, authorization)
        rows = await self._request("GET", f"/voucher/list/{request.shop_id}", list[dict], authorization)
        voucher = next((row for row in rows or [] if str(row.get("id")) == str(request.voucher_id)
                        and str(row.get("shopId")) == str(request.shop_id)), None)
        if not shop or str(shop.get("id")) != str(request.shop_id) or not voucher:
            raise NotFoundError("未找到该商户的优惠券，请重新查询商户和券。")
        # Preserve integer IDs as strings through the browser, and keep money in cents.
        return {"shop_id": str(request.shop_id), "shop_name": shop.get("name") or "商户",
                "voucher_id": str(request.voucher_id),
                **{key: voucher.get(key) for key in (
                    "title", "subTitle", "rules", "payValue", "actualValue", "type", "status", "beginTime", "endTime")}}

    @staticmethod
    def digest(snapshot):
        return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def subscribable(snapshot):
        if str(snapshot["type"]) != "1" or str(snapshot["status"]) != "1":
            raise SubscriptionError("只有上架中的秒杀券可以加入候补，请重新选券。")
        try:
            end = datetime.fromisoformat(snapshot["endTime"])
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone(timedelta(hours=8)))
            if end.timestamp() <= time.time():
                raise ValueError("expired")
            for key in ("payValue", "actualValue"):
                if snapshot[key] is None or int(snapshot[key]) < 0:
                    raise ValueError("unknown price")
        except (ValueError, TypeError, OverflowError) as exc:
            raise SubscriptionError("券已过期或价格、有效期不完整，请到商户页核实。") from exc

    async def _status(self, authorization, voucher_id):
        value = await self._request("POST", "/voucher/get/subscribe/status", int, authorization,
                                    {"voucherId": int(voucher_id)})
        if value not in LABELS:
            raise SubscriptionError("Java 未返回可识别的候补状态，请稍后重新查询。")
        return {"status": value, "status_label": LABELS[value], "verified": True,
                "checked_at": time.time(), "source": "java"}

    async def status(self, owner, authorization, request):
        snapshot = await self.snapshot(owner, authorization, request)
        return {"voucher": snapshot, **await self._status(authorization, request.voucher_id)}

    async def prepare(self, owner, authorization, request):
        snapshot = await self.snapshot(owner, authorization, request)
        if request.action == "subscribe":
            self.subscribable(snapshot)
        current = await self._status(authorization, request.voucher_id)
        now = time.time()
        self.pending = {key: value for key, value in self.pending.items() if value.expires_at > now or value.lock.locked()}
        if len(self.pending) >= 2000:
            raise SubscriptionError("当前待确认操作较多，请稍后重试。")
        action_id = str(uuid4())
        entry = PendingSubscription(owner, request, snapshot, self.digest(snapshot), now + 300)
        self.pending[action_id] = entry
        return {"action_id": action_id, "action": request.action, "voucher": snapshot,
                "expires_at": entry.expires_at, "current": current, "phase": "awaiting_confirmation",
                "notice": NOTICE if request.action == "subscribe" else "只退出候补队列，不会取消已创建的券订单。"}

    async def confirm(self, owner, authorization, action_id, confirmation):
        self.authenticate(owner, authorization)
        entry = self.pending.get(action_id)
        if not entry or entry.owner != owner:
            raise NotFoundError("操作卡不存在或不属于当前账号，请重新准备。")
        async with entry.lock:
            if time.time() >= entry.expires_at:
                raise SubscriptionError("操作卡已过期，请重新查询并准备。")
            if entry.request.action == "subscribe" and not confirmation.accept_auto_issue:
                raise SubscriptionError("请先确认已了解候补可能自动发券、创建券订单。")
            if entry.attempted:
                # Replays can only read status, including after a timeout or later cancellation.
                return await self.receipt(entry, authorization, action_id, replayed=True)
            fresh = await self.snapshot(owner, authorization, entry.request)
            if self.digest(fresh) != entry.digest:
                raise SubscriptionError("券的价格、规则或有效期已变化，请重新准备并确认。")
            if entry.request.action == "subscribe":
                self.subscribable(fresh)
            current = await self._status(authorization, entry.request.voucher_id)
            target = 1 if entry.request.action == "subscribe" else 0
            entry.attempted = True
            if current["status"] not in (target, 2):
                try:
                    await self._request("POST", f"/voucher/{entry.request.action}", dict, authorization,
                                        {"voucherId": entry.request.voucher_id})
                except IntegrationError:
                    # No automatic write retry: even a timed-out call may have been applied.
                    return await self.receipt(entry, authorization, action_id, uncertain=True)
            return await self.receipt(entry, authorization, action_id)

    async def receipt(self, entry, authorization, action_id, *, replayed=False, uncertain=False):
        base = {"action_id": action_id, "action": entry.request.action, "voucher": entry.snapshot,
                "replayed": replayed, "write_outcome_uncertain": uncertain}
        try:
            current = await self._status(authorization, entry.request.voucher_id)
        except (IntegrationError, SubscriptionError):
            return {**base, "phase": "unverified", "verified": False,
                    "message": "操作结果尚未确认，请查询 Java 当前状态；本操作卡不会重复发送写入。"}
        target = 1 if entry.request.action == "subscribe" else 0
        return {**base, **current, "phase": "verified", "target_reached": current["status"] == target,
                "message": "已回查 Java 当前状态。" if current["status"] != 2 else "系统显示已发券并创建订单；取消候补不会取消该订单。"}
