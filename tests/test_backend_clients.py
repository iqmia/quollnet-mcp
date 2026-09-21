import json
import os
import unittest

import httpx

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.services.qapp_client import QAppClient, QAppClientError
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


    async def test_qapp_qtool_write_uses_v2_file_route(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["authorization"] = request.headers.get("Authorization")
            seen["json"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "data": {
                        "path": "js/app.js",
                        "working_version": 2,
                    }
                },
            )

        client = QAppClient()
        client._client = httpx.AsyncClient(
            base_url="https://quollnet.com",
            transport=httpx.MockTransport(handler),
        )
        try:
            result = await client.write_qtool_file(
                access_token="mcp-token",
                slug="concrete-checker",
                relative_path="js/app.js",
                payload={
                    "encoding": "utf-8",
                    "content": "const x = 1;",
                },
            )
        finally:
            await client._client.aclose()
            client._client = None

        self.assertEqual(result["data"]["working_version"], 2)
        self.assertEqual(seen["method"], "PUT")
        self.assertEqual(
            seen["path"],
            "/tools/api/v2/concrete-checker/files/js/app.js",
        )
        self.assertEqual(seen["authorization"], "Bearer mcp-token")
        self.assertEqual(
            seen["json"],
            {
                "encoding": "utf-8",
                "content": "const x = 1;",
            },
        )

    async def test_qapp_qtool_publish_uses_selected_version(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["json"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"data": {"published_version": 3}},
            )

        client = QAppClient()
        client._client = httpx.AsyncClient(
            base_url="https://quollnet.com",
            transport=httpx.MockTransport(handler),
        )
        try:
            result = await client.publish_qtool(
                access_token="mcp-token",
                slug="concrete-checker",
                version=3,
            )
        finally:
            await client._client.aclose()
            client._client = None

        self.assertEqual(result["data"]["published_version"], 3)
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(
            seen["path"],
            "/tools/api/v2/concrete-checker/publish",
        )
        self.assertEqual(seen["json"], {"version": 3})

    async def test_qapp_validation_errors_preserve_error_list(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                422,
                json={
                    "message": "Tool package validation failed",
                    "errors": [
                        "core.html must contain a root",
                        "js/app.js: JavaScript may not use eval()",
                    ],
                },
            )

        client = QAppClient()
        client._client = httpx.AsyncClient(
            base_url="https://quollnet.com",
            transport=httpx.MockTransport(handler),
        )
        try:
            with self.assertRaises(QAppClientError) as ctx:
                await client.save_qtool(
                    access_token="mcp-token",
                    slug="concrete-checker",
                )
        finally:
            await client._client.aclose()
            client._client = None

        message = str(ctx.exception)
        self.assertIn("HTTP 422", message)
        self.assertIn("core.html must contain a root", message)
        self.assertIn("may not use eval()", message)



if __name__ == "__main__":
    unittest.main()
