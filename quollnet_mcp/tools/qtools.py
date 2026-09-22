from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.services.qapp_client import QAppClientError


async def get_qtool_development_guide() -> dict[str, Any]:
    """Return the canonical Quollnet Tools V2 development guide."""
    access_token = get_access_token()

    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    scopes = set(access_token.scopes or [])
    if "qtools:read" not in scopes:
        raise ToolError(
            "The connected account does not have qtools:read permission"
        )

    try:
        return await qapp_client.get_qtool_development_guide(
            access_token=access_token.token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error
