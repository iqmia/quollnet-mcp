from typing import Any

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
            target_app_id=qauth_client.settings.qapp_app_id,
        )
    except QAuthClientError as error:
        raise ToolError(str(error)) from error


async def get_current_user() -> dict[str, Any]:
    """Return the QAuth identity connected to this MCP session."""
    access_token = get_access_token()
    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    claims = access_token.claims or {}
    return {
        "data": {
            "user_id": claims.get("user_id") or access_token.subject,
            "name": claims.get("name"),
            "email": claims.get("email"),
            "app_roles": claims.get("app_roles"),
            "roles": claims.get("roles"),
            "is_active": claims.get("is_active"),
        }
    }
