"""Exchange the current request identity; never cache a user's tokens."""
from uuid import UUID
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.dependencies import qauth_client
from quollnet_mcp.services.qauth_client import QAuthClientError


async def _token(unit_id: str | None = None) -> str:
    access = get_access_token()
    if access is None or not access.subject:
        raise ToolError("Authentication is required")
    settings = qauth_client.settings
    if not settings.qledger_enabled:
        raise ToolError("QLedger is not enabled")
    try:
        return await qauth_client.exchange_app_token(
            mcp_access_token=access.token,
            target_app_id=settings.qledger_app_id,
            unit_id=unit_id,
        )
    except QAuthClientError:
        raise ToolError("QAuth token exchange failed. Reconnect or check QLedger application/unit access.") from None


async def application_token() -> str:
    return await _token()


async def unit_token(unit_id: UUID) -> str:
    return await _token(str(UUID(str(unit_id))))
