"""Run the actual MCP transport, verifier, exchange and adapter against fake upstream HTTP."""

import asyncio
import json
import time
import unittest
from dataclasses import replace
from unittest.mock import patch

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from tests.qledger_support import A, E, U, settings


class QledgerWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticated_rpc_isolation_and_binary_resource(self):
        from mcp.server.transport_security import TransportSecuritySettings

        import combined_app
        from combined_app import build_combined_app
        from quollnet_mcp.cashflowpot.server import build_cashflowpot_server
        from quollnet_mcp.dependencies import (
            qapp_client,
            qauth_client,
            qflow_client,
            qledger_client,
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
        # Give both independent protected resources the same test verification key.
        # The module-level CashflowPot server normally uses environment settings.
        test_cashflowpot = build_cashflowpot_server(configuration)
        test_cashflowpot_app = test_cashflowpot.streamable_http_app(
            streamable_http_path="/",
            json_response=True,
            stateless_http=True,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=["mcp.quollnet.com", "mcp.quollnet.com:*"],
                allowed_origins=["https://chatgpt.com"],
            ),
        )

        minted_tokens = {}

        def token(user, audience="https://mcp.quollnet.com/qledger"):
            if (user, audience) in minted_tokens:
                return minted_tokens[(user, audience)]
            now = int(time.time())
            minted = jwt.encode(
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
            minted_tokens[(user, audience)] = minted
            return minted

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
            if req.url.path.endswith("/load"):
                unit_id = req.url.path.split("/")[-2]
                subject = req.headers["Authorization"].split(" ", 1)[1].split(":")[0]
                return httpx.Response(
                    200, json={"unit": {"id": unit_id}, "token": subject + ":" + unit_id,
                               "parent": None, "children_page": []}
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
            patch.object(combined_app, "cashflowpot_mcp", test_cashflowpot),
            patch.object(combined_app, "_cashflowpot_http_app", test_cashflowpot_app),
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
                    self.assertEqual(len(tools["result"]["tools"]), 60)
                    profiles = [tool for tool in tools["result"]["tools"] if tool.get("_meta", {}).get("openai/profile") is True]
                    self.assertEqual([tool["name"] for tool in profiles], ["get_qledger_profile"])

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
                        {r.headers["Authorization"] for r in requests if not r.url.path.endswith("/load")},
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
                    profile_alice = await rpc(
                        "tools/call", {"name": "get_qledger_profile", "arguments": {}}, user="one"
                    )
                    profile_bob = await rpc(
                        "tools/call", {"name": "get_qledger_profile", "arguments": {}}, user="two"
                    )
                    self.assertEqual(profile_alice["result"]["structuredContent"]["id"], "one")
                    self.assertEqual(profile_bob["result"]["structuredContent"]["id"], "two")
                    self.assertFalse(profile_alice["result"].get("isError", False))
                    self.assertFalse(profile_bob["result"].get("isError", False))
                    profile_again = await rpc(
                        "tools/call", {"name": "get_qledger_profile", "arguments": {}}, user="one"
                    )
                    self.assertEqual(
                        profile_again["result"]["structuredContent"],
                        profile_alice["result"]["structuredContent"],
                    )
                    self.assertNotEqual(
                        profile_alice["result"]["structuredContent"]["id"],
                        profile_bob["result"]["structuredContent"]["id"],
                    )
                    # Profile resolves from verified OAuth JWT, not QAuth exchange.
                    self.assertEqual({e[0] for e in exchanges}, {"one", "two"})
                    cashflowpot = await c.post(
                        "/cashflowpot",
                        headers={
                            "Authorization": "Bearer " + token(
                                "one", "https://mcp.quollnet.com/cashflowpot"
                            ),
                            "Accept": "application/json, text/event-stream",
                        },
                        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                    )
                    self.assertEqual(cashflowpot.status_code, 200, cashflowpot.text)
                    self.assertIn("tools", cashflowpot.json()["result"])
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
