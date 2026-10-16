from typing import Any

from quollnet_mcp.cashflowpot.auth import cashflowpot_token
from quollnet_mcp.cashflowpot.tools.common import call_qflow
from quollnet_mcp.dependencies import qflow_client


async def export_cashflow_excel(unit_id: str, cashflow_id: str) -> dict[str, Any]:
    """Create a short-lived stateless XLSX download link for a cashflow.

    q_flow generates the workbook only when the returned URL is opened. MCP does
    not fetch, cache, base64-encode, or retain the workbook bytes.
    """
    token = await cashflowpot_token(unit_id)
    result = await call_qflow(lambda: qflow_client.request_excel_export(
        access_token=token, cashflow_id=cashflow_id
    ))
    if isinstance(result, dict):
        return {
            **result,
            "message": "Excel export link created. The workbook is generated on download and is not stored on the MCP server.",
        }
    return {"data": result}
