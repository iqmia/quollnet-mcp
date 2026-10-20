"""Submission contracts exercised without touching production projects."""
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from mcp.server.mcpserver.exceptions import ToolError

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.cashflowpot.tools import activities, cashflows, projects
from quollnet_mcp.cashflowpot.models import CashflowInput, PortableCashflowDocument
from quollnet_mcp.services.qflow_client import QFlowClient, QFlowClientError


class EffectivePropertiesTests(unittest.IsolatedAsyncioTestCase):
    async def test_results_include_saved_properties_without_inventing_sources(self):
        snapshot = {
            "id": "cf-1", "unit_id": "unit-1", "name": "Hospital",
            "contract_value": 1500000, "advance": 0.05, "retention": 0.1,
            "release_retention_eop": 0.5, "dlp": 12, "duration_for_payment": 2,
            "wieb": 0.2, "interest_rate": 0.003,
            "use_independent_inflow_curve": True,
            "inflow_curve_type": "linear", "inflow_curve_skew": 0,
            "activities": [{"id": "a-1", "name": "MEP", "cost": 120000,
                            "start": 2, "duration": 10, "advance": 0.15,
                            "cash_flow_json": [1, 2], "created_by": "private-user"}],
            "financing_facilities": [{"id": "f-1", "name": "OD", "type": "Overdraft",
                                      "interest_rate": 0, "fees": 0, "limit": None}],
            "summary": {"peak_pre_financing_need": 42000},
            "created_by": "private-user", "token": "private-token",
        }
        with patch.object(cashflows, "get_cashflow", new=AsyncMock(return_value={"data": snapshot})):
            result = await cashflows.get_cashflow_results("unit-1", "cf-1", detail="full")
        properties = result["properties"]
        self.assertEqual(properties["contract"]["advance"], 0.05)
        self.assertEqual(properties["contract"]["duration_for_payment"], 2)
        self.assertEqual(properties["forecast"]["wieb"], 0.2)
        self.assertEqual(properties["forecast"]["inflow_curve_type"], "linear")
        self.assertEqual(properties["activities"][0]["advance"], 0.15)
        self.assertNotIn("cash_flow_json", properties["activities"][0])
        self.assertEqual(properties["financing"][0]["interest_rate"], 0)
        self.assertIsNone(properties["financing"][0]["limit"])
        self.assertEqual(result["summary"], snapshot["summary"])
        self.assertNotIn("source", json.dumps(properties))
        self.assertNotIn("private-", json.dumps(result))

    async def test_missing_legacy_properties_are_not_fabricated(self):
        with patch.object(cashflows, "get_cashflow", new=AsyncMock(return_value={"data": {"id": "old"}})):
            result = await cashflows.get_cashflow_results("unit-1", "old", detail="full")
        self.assertNotIn("advance", result["properties"]["contract"])
        self.assertNotIn("interest_rate", result["properties"]["forecast"])


class PermanentDeletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirmation_required_before_authentication_or_backend_call(self):
        cases = [
            (projects, "hard_delete_cashflow_project", "hard_delete_project", ("unit-1",)),
            (cashflows, "hard_delete_cashflow", "hard_delete_cashflow", ("unit-1", "cf-1")),
            (activities, "hard_delete_activity", "hard_delete_activity", ("unit-1", "a-1")),
        ]
        for module, name, method, args in cases:
            with self.subTest(tool=name), patch.object(module, "cashflowpot_token", new=AsyncMock()) as auth, patch.object(module.qflow_client, method, new=AsyncMock()) as backend:
                with self.assertRaisesRegex(ToolError, "confirm_permanent"):
                    await getattr(module, name)(*args)
                with self.assertRaisesRegex(ToolError, "confirm_permanent"):
                    await getattr(module, name)(*args, confirm_permanent=False)
                auth.assert_not_awaited()
                backend.assert_not_awaited()

    async def test_confirmed_delete_keeps_scoped_authorization(self):
        with patch.object(cashflows, "cashflowpot_token", new=AsyncMock(return_value="unit-token")) as auth, patch.object(cashflows.qflow_client, "hard_delete_cashflow", new=AsyncMock(return_value={"message": "Cashflow hard deleted successfully"})) as backend:
            result = await cashflows.hard_delete_cashflow("unit-1", "cf-1", confirm_permanent=True)
        auth.assert_awaited_once_with("unit-1")
        backend.assert_awaited_once_with(access_token="unit-token", cashflow_id="cf-1")
        self.assertIn("deleted", result["message"])


class SourceForwardingTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_null_curve_is_preserved_on_create(self):
        with patch.object(cashflows, "cashflowpot_token", new=AsyncMock(return_value="unit-token")), patch.object(cashflows.qflow_client, "import_cashflow", new=AsyncMock(return_value={"data": {"id": "cf-1"}})) as backend:
            await cashflows.create_cashflow("unit-1", CashflowInput(name="Legacy inflow", inflow_curve_type=None))
        source = backend.await_args.kwargs["payload"]["cashflow"]
        self.assertIn("inflow_curve_type", source)
        self.assertIsNone(source["inflow_curve_type"])
        self.assertNotIn("advance", source)

    async def test_portable_import_keeps_markers_and_omitted_source_fields(self):
        document = PortableCashflowDocument(cashflow={"name": "Import", "activities": [{"name": "MEP", "cost": 100, "duration": 2}]})
        with patch.object(cashflows, "cashflowpot_token", new=AsyncMock(return_value="unit-token")), patch.object(cashflows.qflow_client, "import_cashflow", new=AsyncMock(return_value={"data": {"id": "cf-1"}})) as backend:
            await cashflows.import_cashflow_json("unit-1", document)
        payload = backend.await_args.kwargs["payload"]
        self.assertEqual(payload["format"], "cashflowpot.cashflow")
        self.assertEqual(payload["version"], 1)
        self.assertNotIn("activity_type", payload["cashflow"]["activities"][0])


class ErrorMinimizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_upstream_error_details_are_not_echoed(self):
        for status in (400, 401, 403, 404, 409, 422, 500):
            def handler(request):
                return httpx.Response(status, json={"message": "database password=private-secret", "token": "secret"})
            client = QFlowClient()
            client._client = httpx.AsyncClient(base_url="https://cashflowpot.invalid", transport=httpx.MockTransport(handler))
            try:
                with self.assertRaises(QFlowClientError) as caught:
                    await client.get_cashflow(access_token="unit-token", cashflow_id="cf-1")
                self.assertNotIn("private-secret", str(caught.exception))
                self.assertIn(str(status), str(caught.exception))
            finally:
                await client._client.aclose()


if __name__ == "__main__":
    unittest.main()
