from typing import Any

from quollnet_mcp.cashflowpot.auth import cashflowpot_token
from quollnet_mcp.cashflowpot.models import (
    FinancingFacilityInput,
    FinancingFacilityUpdate,
)
from quollnet_mcp.cashflowpot.tools.common import call_qflow
from quollnet_mcp.dependencies import qflow_client


async def list_financing_facility_presets() -> dict[str, Any]:
    """List editable financing facility presets from q_flow."""
    token = await cashflowpot_token()
    return await call_qflow(lambda: qflow_client.list_financing_facility_presets(
        access_token=token
    ))


async def list_financing_facilities(unit_id: str, cashflow_id: str) -> dict[str, Any]:
    """List embedded financing facilities for a cashflow scenario."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.list_financing_facilities(
        access_token=token, cashflow_id=cashflow_id
    ))


async def get_financing_facility(
    unit_id: str, cashflow_id: str, facility_id: str
) -> dict[str, Any]:
    """Get one embedded financing facility by stable ID."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.get_financing_facility(
        access_token=token,
        cashflow_id=cashflow_id,
        facility_id=facility_id,
    ))


async def add_financing_facility(
    unit_id: str,
    cashflow_id: str,
    facility: FinancingFacilityInput,
) -> dict[str, Any]:
    """Add one financing facility to a scenario."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.add_financing_facility(
        access_token=token,
        cashflow_id=cashflow_id,
        payload=facility.model_dump(exclude_none=True),
    ))


async def update_financing_facility(
    unit_id: str,
    cashflow_id: str,
    facility_id: str,
    facility: FinancingFacilityUpdate,
) -> dict[str, Any]:
    """Update one embedded facility without rewriting the facility array."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.update_financing_facility(
        access_token=token,
        cashflow_id=cashflow_id,
        facility_id=facility_id,
        payload=facility.model_dump(exclude_none=True),
    ))


async def delete_financing_facility(
    unit_id: str, cashflow_id: str, facility_id: str
) -> dict[str, Any]:
    """Delete one financing facility from the scenario."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.delete_financing_facility(
        access_token=token,
        cashflow_id=cashflow_id,
        facility_id=facility_id,
    ))


async def set_financing_facility_order(
    unit_id: str, cashflow_id: str, facility_ids: list[str]
) -> dict[str, Any]:
    """Set the complete facility order used by the scenario."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.set_financing_facility_order(
        access_token=token,
        cashflow_id=cashflow_id,
        facility_ids=facility_ids,
    ))
