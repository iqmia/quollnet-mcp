import json
import os
import unittest

import httpx

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.services.qflow_client import QFlowClient


class CashflowPotBackendClientTests(unittest.IsolatedAsyncioTestCase):
    async def _client_call(self, call):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["raw_path"] = request.url.raw_path.decode("ascii")
            seen["query"] = dict(request.url.params)
            seen["authorization"] = request.headers.get("Authorization")
            seen["json"] = (
                json.loads(request.content.decode("utf-8"))
                if request.content
                else None
            )
            return httpx.Response(200, json={"ok": True})

        client = QFlowClient()
        client._client = httpx.AsyncClient(
            base_url="https://cashflowpot.com/api/",
            transport=httpx.MockTransport(handler),
        )
        try:
            result = await call(client)
        finally:
            await client._client.aclose()
            client._client = None
        self.assertTrue(result["ok"])
        self.assertEqual(seen["authorization"], "Bearer unit-token")
        return seen

    async def test_project_id_is_path_escaped(self) -> None:
        seen = await self._client_call(
            lambda client: client.get_project(
                access_token="unit-token", unit_id="unit/with space"
            )
        )
        self.assertEqual(seen["method"], "GET")
        self.assertEqual(seen["raw_path"], "/api/project/unit%2Fwith%20space")

    async def test_cashflow_update_and_export_routes(self) -> None:
        seen = await self._client_call(
            lambda client: client.update_cashflow(
                access_token="unit-token",
                cashflow_id="cf-1",
                payload={"name": "Reforecast"},
            )
        )
        self.assertEqual(seen["method"], "PUT")
        self.assertEqual(seen["path"], "/api/cashflow/cf-1")
        self.assertEqual(seen["json"], {"name": "Reforecast"})

        seen = await self._client_call(
            lambda client: client.export_cashflow(
                access_token="unit-token", cashflow_id="cf-1"
            )
        )
        self.assertEqual(seen["path"], "/api/cashflow/cf-1/export")

    async def test_activity_create_and_restore_many_routes(self) -> None:
        seen = await self._client_call(
            lambda client: client.create_activity(
                access_token="unit-token",
                cashflow_id="cf-1",
                payload={"name": "Structure", "cost": 100, "duration": 2},
            )
        )
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["path"], "/api/new_activity/cf-1")
        self.assertEqual(seen["json"]["name"], "Structure")

        seen = await self._client_call(
            lambda client: client.restore_activities(
                access_token="unit-token", activity_ids=["a-1", "a-2"]
            )
        )
        self.assertEqual(seen["method"], "PUT")
        self.assertEqual(seen["path"], "/api/restore_activities")
        self.assertEqual(seen["json"], {"data": ["a-1", "a-2"]})

    async def test_facility_atomic_routes_and_order(self) -> None:
        seen = await self._client_call(
            lambda client: client.update_financing_facility(
                access_token="unit-token",
                cashflow_id="cf-1",
                facility_id="fac-1",
                payload={"limit": 250000},
            )
        )
        self.assertEqual(seen["method"], "PUT")
        self.assertEqual(seen["path"], "/api/cashflow/cf-1/facilities/fac-1")
        self.assertEqual(seen["json"], {"limit": 250000})

        seen = await self._client_call(
            lambda client: client.set_financing_facility_order(
                access_token="unit-token",
                cashflow_id="cf-1",
                facility_ids=["fac-2", "fac-1"],
            )
        )
        self.assertEqual(seen["path"], "/api/cashflow/cf-1/facilities/order")
        self.assertEqual(seen["json"], {"facility_ids": ["fac-2", "fac-1"]})

    async def test_excel_export_requests_metadata_only(self) -> None:
        seen = await self._client_call(
            lambda client: client.request_excel_export(
                access_token="unit-token", cashflow_id="cf-1"
            )
        )
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["path"], "/api/cashflow/cf-1/excel-export")
        self.assertIsNone(seen["json"])


if __name__ == "__main__":
    unittest.main()
