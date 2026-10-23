"""QLedger application credentials scoped to authenticated ChatGPT connections.

The MCP OAuth token authenticates ChatGPT to this protected resource. Its sole
application use is an initial QAuth exchange on a cache miss; QEntries then
manages unit selection and token refresh.
"""

import json
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, ConfigDict, Field

from quollnet_mcp.dependencies import qauth_client, qledger_client
from quollnet_mcp.services.qauth_client import QAuthClientError
from quollnet_mcp.qledger.qledger_client import QledgerClientError
from quollnet_mcp.qledger import token_store


class QLedgerProfile(BaseModel):
    """Validate the identity returned to ChatGPT without inventing display data."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, pattern=r"\S")
    name: str | None = None
    email: str | None = None


PROFILE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "minLength": 1,
            "pattern": r"\\S",
            "description": "Stable QAuth user ID (OAuth subject).",
        },
        "name": {"type": "string"},
        "email": {"type": "string"},
    },
    "required": ["id"],
    "additionalProperties": False,
}


def get_qledger_profile() -> CallToolResult:
    """Identify the person associated with this request's verified OAuth bearer.

    No model-supplied account selection or QAuth exchange is involved.
    The MCP OAuth subject is the stable QAuth user ID.
    """
    access, _ = _identity()
    claims = access.claims if isinstance(access.claims, dict) else {}
    display = {}
    for key in ("name", "email"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            display[key] = value.strip()
    profile = QLedgerProfile(id=access.subject, **display)
    payload = profile.model_dump(exclude_none=True)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, separators=(",", ":")))],
        structured_content=payload,
    )


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

