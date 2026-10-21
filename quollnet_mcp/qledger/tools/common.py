from uuid import UUID
from pydantic import BaseModel
from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.qledger import auth
from quollnet_mcp.qledger.models import api_payload
from quollnet_mcp.qledger.qledger_client import QledgerClientError


def unit_path(unit_id) -> str:
    return "/api/units/" + str(UUID(str(unit_id)))


def object_id(value) -> str:
    return str(UUID(str(value)))


async def call(
    client,
    method,
    path,
    *,
    unit_id=None,
    body: BaseModel | None = None,
    query: BaseModel | None = None,
    key=None,
):
    token = (
        await auth.unit_token(unit_id)
        if unit_id is not None
        else await auth.application_token()
    )
    try:
        return await client.request(
            method,
            path,
            access_token=token,
            payload=api_payload(body, patch=method == "PATCH")
            if body is not None
            else None,
            params=api_payload(query) if query is not None else None,
            idempotency_key=key,
        )
    except QledgerClientError as error:
        raise ToolError(str(error)) from None
