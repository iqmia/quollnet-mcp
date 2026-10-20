from collections.abc import Callable
from functools import wraps
import json
from typing import Any

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations

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
    @wraps(fn)
    async def public_result(*args: Any, **kwargs: Any) -> CallToolResult:
        # The SDK's default TypedDict converter materializes omitted optional
        # root fields as null, which can violate the advertised schema. Keep
        # the exact sanitized payload in both channels instead.
        result = await fn(*args, **kwargs)
        return CallToolResult(
            content=[TextContent(
                type="text", text=json.dumps(result, ensure_ascii=False, allow_nan=False),
            )],
            structured_content=result,
        )

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
    )(public_result)


def register_cashflowpot_tools(server: MCPServer) -> None:
    registrations = [
        ('list_cashflow_projects', 'List CashflowPot projects',
         'List projects accessible to the connected user, with scenario IDs and names. Supports pagination; returns compact summaries without activity arrays.',
         list_cashflow_projects, True, False),
        ('get_cashflow_project', 'Get CashflowPot project',
         'Retrieve one accessible project and compact summaries of its active forecast scenarios. Use scenario IDs to request detailed properties or calculated results.',
         get_cashflow_project, True, False),
        ('create_cashflow_project', 'Create CashflowPot project',
         'Create a project and an empty Base Cashflow scenario. Optional contract_value sets the base scenario value. Creates persistent data; retrying can create another project.',
         create_cashflow_project, False, False),
        ('update_cashflow_project', 'Update CashflowPot project',
         'Change the selected project name, description or color. Supplied fields overwrite current metadata; omitted fields are retained. Does not change scenario contract terms.',
         update_cashflow_project, False, True),
        ('delete_cashflow_project', 'Delete CashflowPot project',
         'Deactivate the selected project in CashflowPot. Its scenarios become unavailable through normal project access; retained data can be reactivated with restore_cashflow_project.',
         delete_cashflow_project, False, True),
        ('restore_cashflow_project', 'Restore CashflowPot project',
         'Reactivate a previously deactivated project, retaining its saved scenarios and activities. Requires permission to restore that project; does not recover permanently deleted data.',
         restore_cashflow_project, False, False),
        ('hard_delete_cashflow_project', 'Hard-delete CashflowPot project',
         'Permanently delete the identified project, all its scenarios, their activities and embedded financing definitions. This cannot be undone. Requires confirm_permanent=true after explicit user authorization.',
         hard_delete_cashflow_project, False, True),
        ('get_cashflow', 'Get CashflowPot cashflow',
         'Retrieve the complete forecast scenario for detailed activity, financing and period-by-period analysis. Includes all properties and arrays. For funding requirements, financing comparisons or contract negotiation, prefer get_cashflow_results with detail=summary. Read-only.',
         get_cashflow, True, False),
        ('get_cashflow_results', 'Get CashflowPot results',
         'Determine project funding needs, compare financing costs and evaluate payment terms for contract negotiations. Default detail=summary returns authoritative KPIs and compact Cashflow Properties without arrays or activity definitions. Set detail=full for period analysis, charts or complete properties. Read-only.',
         get_cashflow_results, True, False),
        ('create_cashflow', 'Create CashflowPot cashflow',
         'Create a forecast scenario for tender decisions, contract-term negotiation or financing comparisons from contract properties, activities and optional facilities. The backend resolves omitted defaults and calculates results. Returns the full scenario; retrying creates another scenario.',
         create_cashflow, False, False),
        ('update_cashflow', 'Update CashflowPot cashflow',
         'Model how changes in advance, retention, payment delay or other contract/forecast properties affect funding needs. Supplied fields overwrite saved values; omitted fields are retained. Returns recalculated results; activity and facility edits have separate tools.',
         update_cashflow, False, True),
        ('delete_cashflow', 'Delete CashflowPot cashflow',
         'Soft-delete the selected forecast scenario so it is hidden from active project listings. Retains its activities and financing for restore_cashflow; does not permanently erase data.',
         delete_cashflow, False, True),
        ('restore_cashflow', 'Restore CashflowPot cashflow',
         'Restore a soft-deleted forecast scenario to its project. Retains the saved activities and financing definitions; permanently deleted scenarios cannot be restored.',
         restore_cashflow, False, False),
        ('hard_delete_cashflow', 'Hard-delete CashflowPot cashflow',
         'Permanently delete the identified forecast scenario, all its activities and embedded financing definitions. This cannot be undone. Requires confirm_permanent=true after explicit user authorization.',
         hard_delete_cashflow, False, True),
        ('export_cashflow_json', 'Export CashflowPot JSON',
         'Retrieve a version-1 portable source document for the selected scenario, including properties, activities and financing. Excludes cached calculations and ownership data; no file is stored or data changed.',
         export_cashflow_json, True, False),
        ('import_cashflow_json', 'Import CashflowPot JSON',
         'Import a version-1 CashflowPot source document as a new scenario in the selected project. The backend validates inputs, resolves omitted defaults and recalculates results. Existing scenarios are retained; retrying creates another copy.',
         import_cashflow_json, False, False),
        ('get_activity', 'Get CashflowPot activity',
         'Retrieve the saved source properties of one active activity in an accessible project. Returns timing, costs and billing parameters without changing the activity.',
         get_activity, True, False),
        ('get_activity_types', 'Get CashflowPot activity types',
         'List available Work activity categories and their backend forecasting presets, including cost-distribution and billing parameters. Returns guidance for creating activities; no project data is changed.',
         get_activity_types, True, False),
        ('list_deleted_activities', 'List deleted CashflowPot activities',
         'List soft-deleted activities in the selected forecast scenario, including IDs and saved properties needed to choose items to restore. Permanently deleted activities are unavailable.',
         list_deleted_activities, True, False),
        ('create_activity', 'Create CashflowPot activity',
         'Add a Work, Manual Work or Scheduled Cost activity to a forecast and return recalculated results. Manual/scheduled costs use an activity-local amount list; retrying can create another activity.',
         create_activity, False, False),
        ('update_activity', 'Update CashflowPot activity',
         'Change supplied source properties of one active activity and return the recalculated scenario. Omitted fields are retained; supplied values overwrite current timing, costs or billing properties.',
         update_activity, False, True),
        ('delete_activity', 'Delete CashflowPot activity',
         'Soft-delete one activity and recalculate its scenario without it. Saved source data is retained for restore_activity; this changes the forecast immediately.',
         delete_activity, False, True),
        ('restore_activity', 'Restore CashflowPot activity',
         'Restore one soft-deleted activity and recalculate its scenario including it. Permanently deleted activities cannot be recovered; project edit permission is required.',
         restore_activity, False, False),
        ('restore_activities', 'Restore CashflowPot activities',
         'Restore the selected deleted activities within the accessible project and recalculate affected scenarios. Each parent scenario is permission checked; does not recover permanently deleted activities.',
         restore_activities, False, False),
        ('hard_delete_activity', 'Hard-delete CashflowPot activity',
         'Permanently delete the identified activity and recalculate its parent scenario. This cannot be undone. Requires confirm_permanent=true after explicit user authorization.',
         hard_delete_activity, False, True),
        ('list_financing_facility_presets', 'List financing facility presets',
         'List editable financing product presets and their illustrative interest and fixed-fee modeling defaults. Rates are per model period, not bank quotations. Does not modify project data.',
         list_financing_facility_presets, True, False),
        ('list_financing_facilities', 'List financing facilities',
         'List saved financing definitions for the selected scenario, including costs, limits and repayment methods. May assign and persist stable IDs to legacy facilities missing them; does not alter financial properties.',
         list_financing_facilities, False, False),
        ('get_financing_facility', 'Get financing facility',
         'Retrieve one financing definition by its scenario-local ID, including rates, fees, schedules and limits. May assign and persist missing legacy facility IDs before lookup; financial properties are retained.',
         get_financing_facility, False, False),
        ('add_financing_facility', 'Add financing facility',
         'Add a modeled overdraft, progress-certificate discount, letter of credit, loan or owner contribution and recalculate the forecast. Omitted costs use backend defaults. Creates a simulation facility; does not arrange bank funding.',
         add_financing_facility, False, False),
        ('update_financing_facility', 'Update financing facility',
         'Change one modeled financing facility and recalculate the forecast. Supplied fields overwrite its definition and omitted fields are retained. Rates are per model period; fees are fixed currency amounts. No bank transaction occurs.',
         update_financing_facility, False, True),
        ('delete_financing_facility', 'Delete financing facility',
         'Remove one modeled financing facility from the scenario and recalculate funding and costs. The definition is deleted without a restore tool; no real bank facility or money movement is affected.',
         delete_financing_facility, False, True),
        ('set_financing_facility_order', 'Set financing facility order',
         'Replace the scenario facility order and set sweep repayment priorities to that order, then recalculate. Supply every current facility ID exactly once; ordering can change funding and repayment results.',
         set_financing_facility_order, False, True),
        ('export_cashflow_excel', 'Export CashflowPot Excel',
         'Return a short-lived signed Excel download URL and its expiry for the selected forecast. Link creation is stateless; the workbook is generated in memory on download, without storing an artifact or starting a job.',
         export_cashflow_excel, True, False),
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
