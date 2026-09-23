import json
import os
import unittest

import httpx

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.services.qapp_client import QAppClient
from quollnet_mcp.services.qauth_client import QAuthClient
from quollnet_mcp.services.qflow_client import QFlowClient


class BackendClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_qapp_list_qtools_uses_v2_route_and_filters(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["query"] = dict(request.url.params)
            seen["authorization"] = request.headers.get("Authorization")
            return httpx.Response(
                200,
                json={"data": [], "pagination": {"page": 2}},
            )

        client = QAppClient()
        client._client = httpx.AsyncClient(
            base_url="https://quollnet.com",
            transport=httpx.MockTransport(handler),
        )
        try:
            result = await client.list_qtools(
                access_token="mcp-token",
                status="published",
                page=2,
                per_page=10,
            )
        finally:
            await client._client.aclose()
            client._client = None

        self.assertEqual(result["pagination"]["page"], 2)
        self.assertEqual(seen["method"], "GET")
        self.assertEqual(seen["path"], "/tools/api/v2/")
        self.assertEqual(
            seen["query"],
            {
                "page": "2",
                "per_page": "10",
                "status": "published",
            },
        )
        self.assertEqual(seen["authorization"], "Bearer mcp-token")

    async def test_qapp_update_qtool_file_preserves_nested_path(self) -> None:
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
                        "path": "js/01-ui.js",
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
            result = await client.update_qtool_file(
                access_token="mcp-token",
                slug="sample-tool",
                relative_path="js/01-ui.js",
                content="window.ready = true;",
            )
        finally:
            await client._client.aclose()
            client._client = None

        self.assertEqual(result["data"]["working_version"], 2)
        self.assertEqual(seen["method"], "PATCH")
        self.assertEqual(
            seen["path"],
            "/tools/api/v2/sample-tool/files/js/01-ui.js",
        )
        self.assertEqual(seen["authorization"], "Bearer mcp-token")
        self.assertEqual(
            seen["json"],
            {
                "content": "window.ready = true;",
                "encoding": "utf-8",
            },
        )

    async def test_qapp_save_qtool_uses_save_route(self) -> None:
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
                        "slug": "sample-tool",
                        "saved_version": 2,
                    }
                },
            )

        client = QAppClient()
        client._client = httpx.AsyncClient(
            base_url="https://quollnet.com",
            transport=httpx.MockTransport(handler),
        )
        try:
            result = await client.save_qtool(
                access_token="mcp-token",
                slug="sample-tool",
            )
        finally:
            await client._client.aclose()
            client._client = None

        self.assertEqual(result["data"]["saved_version"], 2)
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(
            seen["path"],
            "/tools/api/v2/sample-tool/save",
        )
        self.assertEqual(seen["authorization"], "Bearer mcp-token")
        self.assertEqual(seen["json"], {})

    async def test_qapp_publish_qtool_forwards_explicit_version(self) -> None:
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
                        "slug": "sample-tool",
                        "published_version": 2,
                    }
                },
            )

        client = QAppClient()
        client._client = httpx.AsyncClient(
            base_url="https://quollnet.com",
            transport=httpx.MockTransport(handler),
        )
        try:
            result = await client.publish_qtool(
                access_token="mcp-token",
                slug="sample-tool",
                version=2,
            )
        finally:
            await client._client.aclose()
            client._client = None

        self.assertEqual(result["data"]["published_version"], 2)
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(
            seen["path"],
            "/tools/api/v2/sample-tool/publish",
        )
        self.assertEqual(seen["authorization"], "Bearer mcp-token")
        self.assertEqual(seen["json"], {"version": 2})

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
