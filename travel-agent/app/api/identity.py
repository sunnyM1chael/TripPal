import hashlib
import re
import secrets

from fastapi import Request, Response

from app.core.exceptions import AuthenticationError, IntegrationError
from app.integrations.hmdp.models import AuthContext


async def travel_identity(request: Request, response: Response) -> str:
    container = request.app.state.container
    authorization = request.headers.get("authorization")
    if authorization:
        if len(authorization) > 4096:
            raise AuthenticationError("登录信息无效，请重新登录。")
        try:
            user = await container.hmdp_client.request_data("GET", "/user/me", dict,
                auth=AuthContext(authorization_value=authorization))
        except IntegrationError as exc:
            if exc.details.get("status_code") in {401, 403}:
                raise AuthenticationError("登录已失效，请重新登录。") from exc
            raise
        if not user or not re.fullmatch(r"[1-9]\d{0,19}", str(user.get("id", ""))):
            raise AuthenticationError("无法确认登录身份，请重新登录。")
        return "user:" + str(user["id"])
    token = request.cookies.get("travel_visitor", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,64}", token):
        token = secrets.token_urlsafe(32)
        response.set_cookie("travel_visitor", token, max_age=90 * 86400, httponly=True,
                            secure=container.settings.app_env == "production", samesite="lax", path="/")
    # Neither raw visitor credentials nor Java tokens enter the model context or database.
    return "guest:" + hashlib.sha256(token.encode()).hexdigest()
