import json
import os
import unittest

import httpx

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.services.qauth_client import QAuthClient
from quollnet_mcp.services.qflow_client import QFlowClient


class BackendClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_qauth_exchange_uses_bearer_and_exchange_route(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["authorization"] = request.headers.get("Authorization")
            seen["json"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "access_token": "cashflowpot-user-token",
                    "token_type": "Bearer",
                    "client_app_id": "cashflowpot-test-app",
                },
            )

        client = QAuthClient()
        client._client = httpx.AsyncClient(
            base_url="https://quollnet.com/api",
            transport=httpx.MockTransport(handler),
        )
        try:
            token = await client.exchange_app_token(
                mcp_access_token="mcp-token",
                target_app_id="cashflowpot-test-app",
            )
        finally:
            await client._client.aclose()
            client._client = None

        self.assertEqual(token, "cashflowpot-user-token")
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["path"], "/api/oauth/exchange-app-token")
        self.assertEqual(seen["authorization"], "Bearer mcp-token")
        self.assertEqual(
            seen["json"],
            {"target_app_id": "cashflowpot-test-app"},
        )

    async def test_qflow_import_uses_cashflowpot_token_and_unit_route(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["authorization"] = request.headers.get("Authorization")
            seen["json"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                201,
                json={
                    "message": "Cashflow imported successfully",
                    "data": {"id": "cf-1"},
                },
            )

        client = QFlowClient()
        client._client = httpx.AsyncClient(
            base_url="https://quollnet.com/q_flow/",
            transport=httpx.MockTransport(handler),
        )
        payload = {
            "format": "cashflowpot.cashflow",
            "version": 1,
            "cashflow": {"name": "Tender"},
        }
        try:
            result = await client.import_cashflow(
                access_token="cashflowpot-user-token",
                unit_id="unit-1",
                payload=payload,
            )
        finally:
            await client._client.aclose()
            client._client = None

        self.assertEqual(result["data"]["id"], "cf-1")
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(
            seen["path"],
            "/q_flow/project/unit-1/cashflows/import",
        )
        self.assertEqual(
            seen["authorization"],
            "Bearer cashflowpot-user-token",
        )
        self.assertEqual(seen["json"], payload)


if __name__ == "__main__":
    unittest.main()
