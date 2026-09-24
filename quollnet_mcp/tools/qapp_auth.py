from typing import Any

import jwt
from jwt import InvalidTokenError
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.dependencies import qauth_client
from quollnet_mcp.services.qauth_client import QAuthClientError


async def qapp_user_token() -> str:
    """Exchange the connected Quollnet MCP identity for a normal qApp user token."""
    access_token = get_access_token()
    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    try:
        return await qauth_client.exchange_app_token(
            mcp_access_token=access_token.token,
            target_app_id=qauth_client.settings.qauth_app_id,
        )
    except QAuthClientError as error:
        raise ToolError(str(error)) from error


def qapp_user_identity(token: str) -> dict[str, Any]:
    """Verify a normal qApp token and return its connected-user identity claims."""
    settings = qauth_client.settings

    try:
        claims = jwt.decode(
            token,
            settings.qauth_public_key,
            algorithms=["RS256"],
            audience=settings.qauth_app_id,
            options={
                "require": [
                    "exp",
                    "aud",
                    "user_id",
                    "client_app_id",
                ]
            },
        )
    except (InvalidTokenError, TypeError, ValueError, KeyError) as error:
        raise ToolError("QAuth returned an invalid qApp user token") from error

    if claims.get("client_app_id") != settings.qauth_app_id:
        raise ToolError("QAuth returned a token for the wrong application")

    return {
        "user_id": claims.get("user_id"),
        "name": claims.get("name"),
        "email": claims.get("email"),
        "app_roles": claims.get("app_roles"),
        "roles": claims.get("roles"),
        "is_active": claims.get("is_active"),
    }


async def get_current_user() -> dict[str, Any]:
    """Return the QAuth/qApp identity used by this Quollnet connection."""
    token = await qapp_user_token()
    return {"data": qapp_user_identity(token)}
