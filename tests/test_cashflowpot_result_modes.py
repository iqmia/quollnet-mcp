"""Summary/full decision views and their backend request contracts."""
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
import jsonschema
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.cashflowpot.server import register_cashflowpot_tools
from quollnet_mcp.cashflowpot.tools import cashflows
from quollnet_mcp.services.qflow_client import QFlowClient
from quollnet_mcp.config import get_settings


def compact_backend_response():
    return {"data": {
        "id": "cf-1", "unit_id": "unit-1", "name": "Hospital",
        "summary": {"peak_pre_financing_need": 42000, "peak_unfunded_shortfall": 0,
                    "financing_cost": 1000, "final_facility_outstanding": 500},
        "properties": {
            "contract": {"contract_value": 1500000, "advance": 0.05},
            "forecast": {"wieb": 0.2, "interest_rate": 0.005},
            "activity_counts": {"total": 12, "work": 10, "scheduled_cost": 2},
            "financing": [{"name": "OD", "type": "Overdraft", "limit": 50000,
                           "interest_rate": 0.07 / 12, "fees": 20.83,
                           "draw_schedule": {"0": 1}, "token": "SECRET"}],
            "units": {"interest_rate_basis": "per_model_period", "periods_per_year": None},
            "activities": [{"name": "unneeded details", "cost_schedule_json": [100]}],
        },
        "workflow": [100, 200], "token": "SECRET", "created_by": "PRIVATE",
    }, "token": "SECRET"}


class ResultModesTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_summary_uses_compact_api_and_filters_both_output_channels(self):
        server = MCPServer("result-modes")
        register_cashflowpot_tools(server)
        with patch.object(cashflows, "cashflowpot_token", new=AsyncMock(return_value="unit-token")), patch.object(
            cashflows.qflow_client, "get_cashflow", new=AsyncMock(return_value=compact_backend_response())
        ) as backend:
            response = await server.call_tool("get_cashflow_results", {"unit_id": "unit-1", "cashflow_id": "cf-1"})
        backend.assert_awaited_once_with(access_token="unit-token", cashflow_id="cf-1", detail="summary")
        data = response.structured_content
        self.assertEqual(data["detail"], "summary")
        self.assertEqual(data["summary"]["peak_pre_financing_need"], 42000)
        self.assertEqual(data["properties"]["activity_counts"]["total"], 12)
        self.assertNotIn("activities", data["properties"])
        self.assertNotIn("draw_schedule", data["properties"]["financing"][0])
        self.assertNotIn("workflow", data)
        encoded = json.dumps(response.model_dump(by_alias=True))
        for value in ("SECRET", "PRIVATE", "unneeded details"):
            self.assertNotIn(value, encoded)
        tool = next(t for t in await server.list_tools() if t.name == "get_cashflow_results")
        jsonschema.validate(data, tool.output_schema)

    async def test_client_sends_explicit_summary_query_only_when_requested(self):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(200, json={"data": {}})
        client = QFlowClient(get_settings())
        async with httpx.AsyncClient(base_url="https://cashflowpot.test", transport=httpx.MockTransport(handle)) as http:
            client._client = http
            await client.get_cashflow(access_token="unit-token", cashflow_id="cf/1", detail="summary")
            await client.get_cashflow(access_token="unit-token", cashflow_id="cf/1")
        self.assertEqual(dict(requests[0].url.params), {"detail": "summary"})
        self.assertEqual(dict(requests[1].url.params), {})
        self.assertEqual(requests[0].headers["Authorization"], "Bearer unit-token")

    async def test_invalid_detail_fails_before_authentication(self):
        server = MCPServer("result-modes")
        register_cashflowpot_tools(server)
        with patch.object(cashflows, "cashflowpot_token", new=AsyncMock()) as auth:
            with self.assertRaises(ToolError):
                await server.call_tool("get_cashflow_results", {"unit_id": "unit-1", "cashflow_id": "cf-1", "detail": "everything"})
        auth.assert_not_awaited()

    async def test_stale_backend_summary_does_not_silently_drop_properties(self):
        with patch.object(cashflows, "cashflowpot_token", new=AsyncMock(return_value="unit-token")), patch.object(
            cashflows.qflow_client, "get_cashflow", new=AsyncMock(return_value={"data": {"id": "cf-1", "summary": {}, "workflow": [1]}})
        ):
            with self.assertRaises(ToolError):
                await cashflows.get_cashflow_results("unit-1", "cf-1")

    async def test_advertised_mode_and_nested_kpi_fields_are_typed(self):
        server = MCPServer("result-modes")
        register_cashflowpot_tools(server)
        tools = await server.list_tools()
        self.assertEqual(len(tools), 33)
        tool = next(t for t in tools if t.name == "get_cashflow_results")
        detail = tool.input_schema["properties"]["detail"]
        self.assertEqual(detail["default"], "summary")
        self.assertEqual(detail["enum"], ["summary", "full"])
        schema = tool.output_schema
        summary_ref = schema["properties"]["summary"]["$ref"].split("/")[-1]
        self.assertIn("peak_pre_financing_need", schema["$defs"][summary_ref]["properties"])
        for advertised in tools:
            self.assertTrue(advertised.output_schema.get("properties"))
