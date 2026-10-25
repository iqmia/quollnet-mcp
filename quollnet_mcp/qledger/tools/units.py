from uuid import UUID

from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.qledger import auth
from urllib.parse import quote
from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger.models import UnitCreate, MemberInvite, MemberRoles, PageQuery
from quollnet_mcp.qledger.models_records import RecordQuery
from .common import call, unit_path, object_id


_UNIT_FIELDS = {
    "id",
    "name",
    "description",
    "color",
    "parent_unit_id",
    "is_active",
    "created_at",
    "updated_at",
}


def _unit(value):
    return (
        {
            k: v
            for k, v in value.items()
            if k in _UNIT_FIELDS and isinstance(v, (str, int, float, bool, type(None)))
        }
        if isinstance(value, dict)
        else None
    )


async def list_qledger_units(query: PageQuery = PageQuery()):
    return await call(qledger_client, "GET", "/api/units", query=query)


async def create_qledger_unit(request: UnitCreate):
    result = await call(qledger_client, "POST", "/api/units", body=request)
    if isinstance(result.get("token"), str):
        await auth.remember_unit_token(result["token"], UUID(result["unit"]["id"]))
    return {"unit": _unit(result["unit"])}


async def load_qledger_unit(unit_id: UUID):
    result = await call(qledger_client, "POST", unit_path(unit_id) + "/load")
    if isinstance(result.get("token"), str):
        await auth.remember_unit_token(result["token"], unit_id)
    output = {
        "unit": _unit(result["unit"]),
        "parent": _unit(result.get("parent")),
        "children_page": [_unit(u) for u in result.get("children_page", [])],
    }
    # These live records inherit ordinary record:view and unit-parent view
    # authorization. Loading a unit must not reveal restricted instructions.
    try:
        page = await call(
            qledger_client,
            "GET",
            unit_path(unit_id) + "/records",
            unit_id=unit_id,
            query=RecordQuery(
                page=1,
                per_page=20,
                types="ai_instruction",
                is_template=False,
                is_postable=False,
                linked_to_object="unit",
                linked_to_object_id=str(unit_id),
            ),
        )
    except ToolError as error:
        if str(error).startswith("QLedger HTTP 403:"):
            output["ai_instructions_access"] = "not_authorized"
            return output
        raise
    if not isinstance(page, dict) or not isinstance(page.get("items"), list):
        raise ToolError("QLedger returned an invalid instruction list.")
    output["ai_instructions"] = [
        {"id": row["id"], "version": row["version"], "data": row["data"]}
        for row in page["items"]
        if isinstance(row, dict)
        and row.get("type") == "ai_instruction"
        and row.get("is_postable") is False
    ]
    output["ai_instructions_total"] = page.get("total", len(output["ai_instructions"]))
    return output


async def list_qledger_members(unit_id: UUID, query: PageQuery = PageQuery()):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/members",
        unit_id=unit_id,
        query=query,
    )


async def invite_qledger_member(unit_id: UUID, request: MemberInvite):
    return await call(
        qledger_client,
        "POST",
        unit_path(unit_id) + "/members/invite",
        unit_id=unit_id,
        body=request,
    )


async def remove_qledger_member(unit_id: UUID, user_id: UUID):
    return await call(
        qledger_client,
        "DELETE",
        unit_path(unit_id) + "/members/" + object_id(user_id),
        unit_id=unit_id,
    )


async def list_qledger_roles(unit_id: UUID):
    return await call(
        qledger_client, "GET", unit_path(unit_id) + "/roles", unit_id=unit_id
    )


async def add_qledger_member_roles(unit_id: UUID, user_id: UUID, request: MemberRoles):
    return await call(
        qledger_client,
        "POST",
        unit_path(unit_id) + "/members/" + object_id(user_id) + "/roles",
        unit_id=unit_id,
        body=request,
    )


async def remove_qledger_member_role(unit_id: UUID, user_id: UUID, role_name: str):
    if not role_name or len(role_name) > 100 or role_name in (".", ".."):
        raise ValueError("Invalid role name")
    return await call(
        qledger_client,
        "DELETE",
        unit_path(unit_id)
        + "/members/"
        + object_id(user_id)
        + "/roles/"
        + quote(role_name, safe=""),
        unit_id=unit_id,
    )
