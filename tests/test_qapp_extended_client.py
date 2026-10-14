import json
import os
import unittest

import httpx

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.services.qapp_extended_client import QAppExtendedClient


class QAppExtendedClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_json_sends_json_body_and_bearer_token(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["authorization"] = request.headers.get("Authorization")
            seen["json"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"message": "Article deleted"})

        client = QAppExtendedClient()
        client._client = httpx.AsyncClient(
            base_url="https://quollnet.com",
            transport=httpx.MockTransport(handler),
        )
        try:
            result = await client.delete_json(
                "/articles/api/v1/articles/delete",
                payload={"id": "article-1"},
                access_token="qapp-user-token",
            )
        finally:
            await client._client.aclose()
            client._client = None

        self.assertEqual(result["message"], "Article deleted")
        self.assertEqual(seen["method"], "DELETE")
        self.assertEqual(seen["path"], "/articles/api/v1/articles/delete")
        self.assertEqual(seen["authorization"], "Bearer qapp-user-token")
        self.assertEqual(seen["json"], {"id": "article-1"})


if __name__ == "__main__":
    unittest.main()
