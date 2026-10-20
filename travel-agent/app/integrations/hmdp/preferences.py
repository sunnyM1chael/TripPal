"""Java owns account preferences; Python never accepts a user id for these writes."""
from app.core.exceptions import AuthenticationError, UpstreamProtocolError
from app.integrations.hmdp.models import AuthContext
from app.memory.models import Preferences
from pydantic import ValidationError


class PreferenceGateway:
    def __init__(self, client):
        self.client = client

    async def get(self, owner, authorization):
        if owner.startswith("guest:"):
            return {}
        return await self._request("GET", owner, authorization)

    async def update(self, owner, authorization, patch):
        return await self._request("PATCH", owner, authorization,
                                   Preferences.model_validate(patch).model_dump(exclude_unset=True))

    async def clear(self, owner, authorization):
        if not owner.startswith("guest:"):
            await self._request("DELETE", owner, authorization)

    async def _request(self, method, owner, authorization, patch=None):
        if not owner.startswith("user:") or not authorization:
            raise AuthenticationError("请先登录，再保存长期出行偏好。")
        data = await self.client.request_data(method, "/user/travel-preferences", dict,
            auth=AuthContext(authorization_value=authorization), json=patch)
        if method == "DELETE":
            return {}
        if data is None:
            raise UpstreamProtocolError("用户偏好接口未返回数据。")
        # Normalize Java's null-number/null-string representation only on reads.
        # An unset transport is not an invalid user-supplied transport selection.
        data = dict(data)
        for field in ("budget_per_person", "transport"):
            if data.get(field) == "":
                data[field] = None
        try:
            return Preferences.model_validate(data).model_dump(exclude_none=True)
        except ValidationError as exc:
            raise UpstreamProtocolError("用户偏好接口返回了无效数据。") from exc
