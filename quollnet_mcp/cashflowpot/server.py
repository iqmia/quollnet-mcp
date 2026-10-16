from collections.abc import Callable
from typing import Any

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from mcp.types import ToolAnnotations

from quollnet_mcp.auth import QAuthTokenVerifier
from quollnet_mcp.cashflowpot.instructions import CASHFLOWPOT_INSTRUCTIONS
from quollnet_mcp.cashflowpot.tools.activities import (
    create_activity,
    delete_activity,
    get_activity,
    get_activity_types,
    hard_delete_activity,
    list_deleted_activities,
    restore_activities,
    restore_activity,
    update_activity,
)
from quollnet_mcp.cashflowpot.tools.cashflows import (
    create_cashflow,
    delete_cashflow,
    export_cashflow_json,
    get_cashflow,
    get_cashflow_results,
    hard_delete_cashflow,
    import_cashflow_json,
    restore_cashflow,
    update_cashflow,
)
from quollnet_mcp.cashflowpot.tools.exports import export_cashflow_excel
from quollnet_mcp.cashflowpot.tools.facilities import (
    add_financing_facility,
    delete_financing_facility,
    get_financing_facility,
    list_financing_facilities,
    list_financing_facility_presets,
    set_financing_facility_order,
    update_financing_facility,
)
from quollnet_mcp.cashflowpot.tools.projects import (
    create_cashflow_project,
    delete_cashflow_project,
    get_cashflow_project,
    hard_delete_cashflow_project,
    list_cashflow_projects,
    restore_cashflow_project,
    update_cashflow_project,
)
from quollnet_mcp.config import Settings


def _register(
    server: MCPServer,
    *,
    name: str,
    title: str,
    description: str,
    fn: Callable[..., Any],
    read_only: bool = False,
    destructive: bool = False,
) -> None:
    server.tool(
        name=name,
        title=title,
        description=description,
        annotations=ToolAnnotations(
            read_only_hint=read_only,
            destructive_hint=destructive,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": [{"type": "oauth2", "scopes": ["mcp:connect"]}],
            "openai/toolInvocation/invoking": title,
            "openai/toolInvocation/invoked": f"{title} complete",
        },
    )(fn)


def register_cashflowpot_tools(server: MCPServer) -> None:
    registrations = [
        ("list_cashflow_projects", "List CashflowPot projects", "List projects and compact scenarios.", list_cashflow_projects, True, False),
        ("get_cashflow_project", "Get CashflowPot project", "Get a project with its active scenarios.", get_cashflow_project, True, False),
        ("create_cashflow_project", "Create CashflowPot project", "Create a project and base cashflow.", create_cashflow_project, False, False),
        ("update_cashflow_project", "Update CashflowPot project", "Update project metadata.", update_cashflow_project, False, False),
        ("delete_cashflow_project", "Delete CashflowPot project", "Soft-delete/deactivate a project.", delete_cashflow_project, False, True),
        ("restore_cashflow_project", "Restore CashflowPot project", "Restore/reactivate a project.", restore_cashflow_project, False, False),
        ("hard_delete_cashflow_project", "Hard-delete CashflowPot project", "Permanently delete a project and its local scenarios.", hard_delete_cashflow_project, False, True),
        ("get_cashflow", "Get CashflowPot cashflow", "Get one authoritative scenario including activities and results.", get_cashflow, True, False),
        ("get_cashflow_results", "Get CashflowPot results", "Get calculation-focused authoritative scenario results.", get_cashflow_results, True, False),
        ("create_cashflow", "Create CashflowPot cashflow", "Create a complete scenario from source inputs.", create_cashflow, False, False),
        ("update_cashflow", "Update CashflowPot cashflow", "Update scenario-level assumptions.", update_cashflow, False, False),
        ("delete_cashflow", "Delete CashflowPot cashflow", "Soft-delete a scenario.", delete_cashflow, False, True),
        ("restore_cashflow", "Restore CashflowPot cashflow", "Restore a soft-deleted scenario.", restore_cashflow, False, False),
        ("hard_delete_cashflow", "Hard-delete CashflowPot cashflow", "Permanently delete a scenario and its activities.", hard_delete_cashflow, False, True),
        ("export_cashflow_json", "Export CashflowPot JSON", "Return the canonical shareable version-1 scenario document.", export_cashflow_json, True, False),
        ("import_cashflow_json", "Import CashflowPot JSON", "Import a canonical shareable scenario document into a project.", import_cashflow_json, False, False),
        ("get_activity", "Get CashflowPot activity", "Get one active activity.", get_activity, True, False),
        ("get_activity_types", "Get CashflowPot activity types", "List backend activity type presets.", get_activity_types, True, False),
        ("list_deleted_activities", "List deleted CashflowPot activities", "List soft-deleted activities in a scenario.", list_deleted_activities, True, False),
        ("create_activity", "Create CashflowPot activity", "Create Work, Manual Work, or Scheduled Cost activity source data.", create_activity, False, False),
        ("update_activity", "Update CashflowPot activity", "Update activity source data and recalculate the scenario.", update_activity, False, False),
        ("delete_activity", "Delete CashflowPot activity", "Soft-delete an activity.", delete_activity, False, True),
        ("restore_activity", "Restore CashflowPot activity", "Restore one soft-deleted activity.", restore_activity, False, False),
        ("restore_activities", "Restore CashflowPot activities", "Restore multiple activities by ID.", restore_activities, False, False),
        ("hard_delete_activity", "Hard-delete CashflowPot activity", "Permanently delete an activity.", hard_delete_activity, False, True),
        ("list_financing_facility_presets", "List financing facility presets", "List editable q_flow financing presets.", list_financing_facility_presets, True, False),
        ("list_financing_facilities", "List financing facilities", "List facilities embedded in a cashflow scenario.", list_financing_facilities, True, False),
        ("get_financing_facility", "Get financing facility", "Get one embedded facility by stable ID.", get_financing_facility, True, False),
        ("add_financing_facility", "Add financing facility", "Add one facility to a scenario.", add_financing_facility, False, False),
        ("update_financing_facility", "Update financing facility", "Update one facility without replacing the entire array.", update_financing_facility, False, False),
        ("delete_financing_facility", "Delete financing facility", "Delete one embedded facility.", delete_financing_facility, False, True),
        ("set_financing_facility_order", "Set financing facility order", "Set the complete facility order used by a scenario.", set_financing_facility_order, False, False),
        ("export_cashflow_excel", "Export CashflowPot Excel", "Create a short-lived signed XLSX download URL; the workbook is generated in memory by q_flow when downloaded.", export_cashflow_excel, True, False),
    ]
    for name, title, description, fn, read_only, destructive in registrations:
        _register(
            server,
            name=name,
            title=title,
            description=description,
            fn=fn,
            read_only=read_only,
            destructive=destructive,
        )


def build_cashflowpot_server(settings: Settings) -> MCPServer:
    server = MCPServer(
        "cashflowpot-mcp",
        version=settings.service_version,
        instructions=CASHFLOWPOT_INSTRUCTIONS,
        token_verifier=QAuthTokenVerifier(
            issuer_url=settings.qauth_issuer_url,
            resource_uri=settings.cashflowpot_mcp_resource_uri,
            app_id=settings.qauth_app_id,
            public_key=settings.qauth_public_key,
        ),
        auth=AuthSettings(
            issuer_url=settings.qauth_issuer_url,
            resource_server_url=settings.cashflowpot_mcp_resource_uri,
            required_scopes=["mcp:connect"],
        ),
    )
    register_cashflowpot_tools(server)
    return server
