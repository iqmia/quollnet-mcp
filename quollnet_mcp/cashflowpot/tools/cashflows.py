from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.cashflowpot.parameters import ProjectId, CashflowId, ConfirmPermanent, ResultDetail
from quollnet_mcp.cashflowpot.responses import CashflowResponse, CompactResultsResponse, MessageResponse, PortableResponse, ResultsResponse, project_response
from quollnet_mcp.cashflowpot.auth import cashflowpot_token
from quollnet_mcp.cashflowpot.models import (
    CashflowInput,
    CashflowUpdate,
    PortableCashflowDocument,
)
from quollnet_mcp.cashflowpot.tools.common import call_qflow, require_permanent_confirmation
from quollnet_mcp.dependencies import qflow_client


async def get_cashflow(unit_id: ProjectId, cashflow_id: CashflowId) -> CashflowResponse:
    """Get the authoritative CashflowPot scenario including activities/results."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(CashflowResponse, lambda: qflow_client.get_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def get_cashflow_results(
    unit_id: ProjectId, cashflow_id: CashflowId, detail: ResultDetail = "summary",
) -> ResultsResponse:
    """Analyze funding needs, financing choices and payment terms using backend KPIs."""
    if detail not in {"summary", "full"}:
        raise ToolError("detail must be summary or full")
    if detail == "summary":
        token = await cashflowpot_token(unit_id)
        response = await call_qflow(CompactResultsResponse, lambda: qflow_client.get_cashflow(
            access_token=token, cashflow_id=cashflow_id, detail="summary",
        ))
        return project_response({**response["data"], "detail": "summary"}, ResultsResponse)

    response = await get_cashflow(unit_id, cashflow_id)
    data = response.get("data", response) if isinstance(response, dict) else response
    if not isinstance(data, dict):
        raise ToolError("CashflowPot returned an invalid scenario response.")
    keys = (
        "id", "unit_id", "name", "summary", "workflow", "inflow", "outflow",
        "netflow", "pre_financing_balance", "facility_rows", "facility_inflow",
        "facility_outflow", "facility_interest", "facility_fees",
        "funded_netflow", "unfunded_shortfall", "outflow_with_interest",
    )
    contract_keys = (
        "contract_value", "advance", "retention", "release_retention_eop",
        "dlp", "duration_for_payment",
    )
    forecast_keys = (
        "wieb", "interest_rate", "use_independent_inflow_curve",
        "inflow_curve_type", "inflow_curve_skew",
    )
    # Only expose values supplied by q_flow. Do not infer defaults or provenance.
    result = {key: data[key] for key in keys if key in data}
    result["detail"] = "full"
    result["properties"] = {
        "contract": {key: data[key] for key in contract_keys if key in data},
        "forecast": {key: data[key] for key in forecast_keys if key in data},
        "activities": data.get("activities", []),
        "financing": data.get("financing_facilities", []),
        "units": {
            "percentages": "fraction", "period_index_base": 0,
            "period_unit": "model_period", "amount_unit": "project_currency",
            "interest_rate_basis": "per_model_period",
            "periods_per_year": None,
        },
    }
    return project_response(result, ResultsResponse)


async def create_cashflow(unit_id: ProjectId, cashflow: CashflowInput) -> CashflowResponse:
    """Create a complete scenario from source inputs; q_flow recalculates it."""
    token = await cashflowpot_token(unit_id)
    source = cashflow.model_dump(exclude_none=True)
    # These nullable settings deliberately select legacy curve behavior. Omitted
    # optional input fields still belong to q_flow's default resolution.
    for field in ("use_independent_inflow_curve", "inflow_curve_type", "inflow_curve_skew"):
        if field in cashflow.model_fields_set:
            source[field] = getattr(cashflow, field)
    payload = {
        "format": "cashflowpot.cashflow",
        "version": 1,
        "cashflow": source,
    }
    return await call_qflow(CashflowResponse, lambda: qflow_client.import_cashflow(
        access_token=token, unit_id=unit_id, payload=payload
    ))


async def update_cashflow(
    unit_id: ProjectId, cashflow_id: CashflowId, cashflow: CashflowUpdate
) -> CashflowResponse:
    """Update scenario-level commercial and forecasting properties."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(CashflowResponse, lambda: qflow_client.update_cashflow(
        access_token=token,
        cashflow_id=cashflow_id,
        payload=cashflow.model_dump(exclude_unset=True),
    ))


async def delete_cashflow(unit_id: ProjectId, cashflow_id: CashflowId) -> MessageResponse:
    """Soft-delete a scenario."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(MessageResponse, lambda: qflow_client.delete_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def restore_cashflow(unit_id: ProjectId, cashflow_id: CashflowId) -> MessageResponse:
    """Restore a soft-deleted scenario."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(MessageResponse, lambda: qflow_client.restore_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def hard_delete_cashflow(
    unit_id: ProjectId, cashflow_id: CashflowId,
    confirm_permanent: ConfirmPermanent = False,
) -> MessageResponse:
    """Permanently delete a scenario and its activities."""
    require_permanent_confirmation(confirm_permanent)
    token = await cashflowpot_token(unit_id)
    return await call_qflow(MessageResponse, lambda: qflow_client.hard_delete_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def export_cashflow_json(unit_id: ProjectId, cashflow_id: CashflowId) -> PortableResponse:
    """Return the canonical portable CashflowPot version-1 JSON document."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(PortableResponse, lambda: qflow_client.export_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def import_cashflow_json(
    unit_id: ProjectId, document: PortableCashflowDocument
) -> CashflowResponse:
    """Import a shareable CashflowPot JSON scenario into a project."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(CashflowResponse, lambda: qflow_client.import_cashflow(
        access_token=token,
        unit_id=unit_id,
        payload={
            "format": document.format,
            "version": document.version,
            "cashflow": document.cashflow.model_dump(exclude_unset=True),
        },
    ))
