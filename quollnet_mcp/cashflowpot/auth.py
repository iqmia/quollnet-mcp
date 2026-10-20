from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.cashflowpot.token_store import get_cashflowpot_app_token
from quollnet_mcp.dependencies import qauth_client
from quollnet_mcp.services.qauth_client import QAuthClientError


async def cashflowpot_token(unit_id: str | None = None) -> str:
    """Return the current CashflowPot token for this authenticated MCP connection.

    The first call exchanges the OAuth identity for a CashflowPot *user* token.
    q_flow subsequently handles Unit loading and token refresh, returning new
    tokens with API responses; the MCP stores those automatically. unit_id is
    retained for tool compatibility, not used in the initial exchange.
    """
    access_token = get_access_token()
    if access_token is None or not access_token.subject or not access_token.token:
        raise ToolError("Authentication is required")

    try:
        return await get_cashflowpot_app_token(
            oauth_token=access_token.token,
            subject=access_token.subject,
            app_id=qauth_client.settings.cashflowpot_app_id,
            oauth_expires_at=access_token.expires_at,
            exchange=lambda: qauth_client.exchange_app_token(
                mcp_access_token=access_token.token,
                target_app_id=qauth_client.settings.cashflowpot_app_id,
                unit_id=None,
            ),
        )
    except (QAuthClientError, ValueError) as error:
        raise ToolError(
            "CashflowPot authorization failed. Reconnect or check your project access."
        ) from error
