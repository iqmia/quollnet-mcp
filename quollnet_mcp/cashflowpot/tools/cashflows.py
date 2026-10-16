from typing import Any

from quollnet_mcp.cashflowpot.auth import cashflowpot_token
from quollnet_mcp.cashflowpot.models import (
    CashflowInput,
    CashflowUpdate,
    PortableCashflowDocument,
)
from quollnet_mcp.cashflowpot.tools.common import call_qflow
from quollnet_mcp.dependencies import qflow_client


async def get_cashflow(unit_id: str, cashflow_id: str) -> dict[str, Any]:
    """Get the authoritative CashflowPot scenario including activities/results."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.get_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def get_cashflow_results(unit_id: str, cashflow_id: str) -> dict[str, Any]:
    """Return calculation-focused authoritative results for a scenario."""
    response = await get_cashflow(unit_id, cashflow_id)
    data = response.get("data", response) if isinstance(response, dict) else response
    if not isinstance(data, dict):
        return {"data": data}
    keys = (
        "id", "unit_id", "name", "summary", "workflow", "inflow", "outflow",
        "netflow", "pre_financing_balance", "facility_rows", "facility_inflow",
        "facility_outflow", "facility_interest", "facility_fees",
        "funded_netflow", "unfunded_shortfall", "outflow_with_interest",
    )
    return {key: data[key] for key in keys if key in data}


async def create_cashflow(unit_id: str, cashflow: CashflowInput) -> dict[str, Any]:
    """Create a complete scenario from source inputs; q_flow recalculates it."""
    token = await cashflowpot_token(unit_id)
    payload = {
        "format": "cashflowpot.cashflow",
        "version": 1,
        "cashflow": cashflow.model_dump(exclude_none=True),
    }
    return await call_qflow(lambda: qflow_client.import_cashflow(
        access_token=token, unit_id=unit_id, payload=payload
    ))


async def update_cashflow(
    unit_id: str, cashflow_id: str, cashflow: CashflowUpdate
) -> dict[str, Any]:
    """Update scenario-level commercial/inflow assumptions."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.update_cashflow(
        access_token=token,
        cashflow_id=cashflow_id,
        payload=cashflow.model_dump(exclude_none=True),
    ))


async def delete_cashflow(unit_id: str, cashflow_id: str) -> dict[str, Any]:
    """Soft-delete a scenario."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.delete_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def restore_cashflow(unit_id: str, cashflow_id: str) -> dict[str, Any]:
    """Restore a soft-deleted scenario."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.restore_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def hard_delete_cashflow(unit_id: str, cashflow_id: str) -> dict[str, Any]:
    """Permanently delete a scenario and its activities."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.hard_delete_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def export_cashflow_json(unit_id: str, cashflow_id: str) -> dict[str, Any]:
    """Return the canonical portable CashflowPot version-1 JSON document."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.export_cashflow(
        access_token=token, cashflow_id=cashflow_id
    ))


async def import_cashflow_json(
    unit_id: str, document: PortableCashflowDocument
) -> dict[str, Any]:
    """Import a shareable CashflowPot JSON scenario into a project."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.import_cashflow(
        access_token=token,
        unit_id=unit_id,
        payload=document.model_dump(),
    ))
