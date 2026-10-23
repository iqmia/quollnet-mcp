"""QLedger application credentials scoped to authenticated ChatGPT connections.

The MCP OAuth token authenticates ChatGPT to this protected resource. Its sole
application use is an initial QAuth exchange on a cache miss; QEntries then
manages unit selection and token refresh.
"""

from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from typing import Annotated, NotRequired, TypedDict
from pydantic import ConfigDict, Field

from quollnet_mcp.dependencies import qauth_client, qledger_client
from quollnet_mcp.services.qauth_client import QAuthClientError
from quollnet_mcp.qledger.qledger_client import QledgerClientError
from quollnet_mcp.qledger import token_store

class QLedgerProfile(TypedDict):
    """Authenticated stable profile for ChatGPT native multi-account support."""

    __pydantic_config__ = ConfigDict(extra="forbid")

    id: Annotated[str, Field(min_length=1, pattern=r"\S")]
    name: NotRequired[str]
    email: NotRequired[str]


def get_qledger_profile() -> QLedgerProfile:
    """Return the account represented by THIS request's verified OAuth token.

    No model-supplied account selection, token exchange, or QEntries call is
    involved. QAuth user ID (sub) is stable across account reconnections.
    """
    access, _ = _identity()
    claims = access.claims if isinstance(access.claims, dict) else {}
    result: QLedgerProfile = {"id": access.subject}
    for key in ("name", "email"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


def _identity():
    access = get_access_token()
    if access is None or not access.subject or not access.token:
        raise ToolError("Authentication is required")
    if not qauth_client.settings.qledger_enabled:
        raise ToolError("QLedger is not enabled")
    return access, qauth_client.settings.qledger_app_id


async def _exchange(access, app_id: str) -> str:
    return await qauth_client.exchange_app_token(
        mcp_access_token=access.token, target_app_id=app_id, unit_id=None
    )


async def _refresh(token: str) -> str:
    data = await qledger_client.request(
        "POST", "/api/auth/refresh", access_token=token
    )
    if not isinstance(data, dict) or not isinstance(data.get("token"), str):
        raise ValueError("QEntries returned an invalid refreshed token")
    return data["token"]


async def _load(user_token: str, unit_id: str) -> str:
    data = await qledger_client.request(
        "POST", f"/api/units/{unit_id}/load", access_token=user_token
    )
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("unit"), dict)
        or str(data["unit"].get("id")) != unit_id
        or not isinstance(data.get("token"), str)
    ):
        raise ValueError("QEntries returned an invalid unit token response")
    return data["token"]


def _tool_error(error: Exception):
    if isinstance(error, ValueError):
        raise ToolError(str(error)) from None
    if isinstance(error, QledgerClientError):
        raise ToolError(str(error)) from None
    raise ToolError(
        "QLedger authorization failed. Reconnect or check application and unit access."
    ) from None


async def application_token() -> str:
    access, app_id = _identity()
    try:
        return await token_store.user_token(
            access, app_id,
            exchange=lambda: _exchange(access, app_id),
            refresh=_refresh,
        )
    except (ValueError, QAuthClientError, QledgerClientError) as error:
        _tool_error(error)


async def unit_token(unit_id: UUID) -> str:
    access, app_id = _identity()
    uid = str(UUID(str(unit_id)))
    try:
        return await token_store.unit_token(
            access, app_id, uid,
            exchange=lambda: _exchange(access, app_id),
            refresh=_refresh,
            load=_load,
        )
    except (ValueError, QAuthClientError, QledgerClientError) as error:
        _tool_error(error)


async def remember_unit_token(token: str, unit_id: UUID) -> None:
    await token_store.remember_unit_token(token, str(UUID(str(unit_id))))

