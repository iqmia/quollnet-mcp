from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.dependencies import qauth_client
from quollnet_mcp.services.qauth_client import QAuthClientError


async def cashflowpot_token(unit_id: str | None = None) -> str:
    """Exchange the connected MCP identity for a normal CashflowPot token."""
    access_token = get_access_token()
    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    try:
        return await qauth_client.exchange_app_token(
            mcp_access_token=access_token.token,
            target_app_id=qauth_client.settings.cashflowpot_app_id,
            unit_id=unit_id,
        )
    except QAuthClientError as error:
        raise ToolError(
            "CashflowPot authorization failed. Reconnect or check your project access."
        ) from error
