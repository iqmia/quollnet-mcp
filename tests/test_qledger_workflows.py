"""Run the actual MCP transport, verifier, exchange and adapter against fake upstream HTTP."""

import asyncio
import json
import time
import unittest
from dataclasses import replace
from unittest.mock import patch
import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from tests.qledger_support import U, E, A, settings


class QledgerWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticated_rpc_isolation_and_binary_resource(self):
        from combined_app import build_combined_app
        from quollnet_mcp.dependencies import (
            qledger_client,
            qauth_client,
            qapp_client,
            qflow_client,
        )

        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = (
            private.public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        configuration = replace(settings(), qauth_public_key=public)

        def token(user, audience="https://mcp.quollnet.com/qledger"):
            now = int(time.time())
            return jwt.encode(
                {
                    "iss": configuration.qauth_issuer_url,
                    "sub": user,
                    "user_id": user,
                    "aud": audience,
                    "scope": "mcp:connect",
                    "token_use": "mcp_access",
                    "client_app_id": configuration.qauth_app_id,
                    "iat": now,
                    "nbf": now - 1,
                    "exp": now + 600,
                },
                private,
                algorithm="RS256",
                headers={"kid": configuration.qauth_app_id, "typ": "JWT"},
            )

        exchanges = []
        requests = []

        def exchange(req):
            claims = jwt.decode(
                req.headers["Authorization"][7:],
                public,
                algorithms=["RS256"],
                audience=configuration.qledger_mcp_resource_uri,
            )
            body = json.loads(req.content)
            exchanges.append((claims["sub"], body))
            return httpx.Response(
                200,
                json={"access_token": claims["sub"] + ":" + body.get("unit_id", "app")},
            )

        async def ledger(req):
            await asyncio.sleep(0)
            requests.append(req)
            if req.url.path.endswith("/download"):
                return httpx.Response(
                    200, content=b"pdf", headers={"content-type": "application/pdf"}
                )
            return httpx.Response(
                200, json={"items": [], "total": 0, "page": 1, "per_page": 50}
            )

        qa = httpx.AsyncClient(
            transport=httpx.MockTransport(exchange), base_url="https://quollnet.com/api"
        )
        ql = httpx.AsyncClient(
            transport=httpx.MockTransport(ledger), base_url="https://ledger.test"
        )
        unused_app = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(500))
        )
        unused_flow = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(500))
        )
        with (
            patch.object(qapp_client, "_client", unused_app),
            patch.object(qflow_client, "_client", unused_flow),
            patch.object(qauth_client, "settings", configuration),
            patch.object(qauth_client, "_client", qa),
            patch.object(qledger_client, "settings", configuration),
            patch.object(qledger_client, "_client", ql),
        ):
            app = build_combined_app(configuration)
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="https://mcp.quollnet.com",
                ) as c:

                    async def rpc(
                        method,
                        params,
                        user="one",
                        audience="https://mcp.quollnet.com/qledger",
                    ):
                        r = await c.post(
                            "/qledger",
                            headers={
                                "Authorization": "Bearer " + token(user, audience),
                                "Accept": "application/json, text/event-stream",
                            },
                            json={
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": method,
                                "params": params,
                            },
                        )
                        self.assertEqual(r.status_code, 200, r.text)
                        return r.json()

                    init = await rpc(
                        "initialize",
                        {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1"},
                        },
                    )
                    self.assertEqual(
                        init["result"]["serverInfo"]["name"], "qledger-mcp"
                    )
                    tools = await rpc("tools/list", {})
                    self.assertEqual(len(tools["result"]["tools"]), 51)
                    results = await asyncio.gather(
                        rpc(
                            "tools/call",
                            {
                                "name": "list_qledger_accounts",
                                "arguments": {"unit_id": U},
                            },
                            "one",
                        ),
                        rpc(
                            "tools/call",
                            {
                                "name": "list_qledger_accounts",
                                "arguments": {"unit_id": E},
                            },
                            "two",
                        ),
                    )
                    self.assertTrue(
                        all(not r["result"].get("isError", False) for r in results),
                        results,
                    )
                    self.assertEqual(
                        {r.headers["Authorization"] for r in requests},
                        {"Bearer one:" + U, "Bearer two:" + E},
                    )
                    self.assertEqual(
                        {e[1]["target_app_id"] for e in exchanges}, {"ledger-app"}
                    )
                    resource = await rpc(
                        "resources/read",
                        {"uri": f"qledger://units/{U}/attachments/{A}"},
                    )
                    self.assertEqual(resource["result"]["contents"][0]["blob"], "cGRm")
                    before = len(exchanges)
                    bad = await c.post(
                        "/qledger",
                        headers={
                            "Authorization": "Bearer "
                            + token("one", "https://mcp.quollnet.com/cashflowpot")
                        },
                        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                    )
                    self.assertEqual(bad.status_code, 401)
                    self.assertEqual(len(exchanges), before)
            self.assertIsNone(qledger_client._client)
            self.assertIsNone(qauth_client._client)
