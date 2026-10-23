"""QLedger-only session lifecycle; deliberately no CashflowPot implementation changes."""

import time
import unittest
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from tests.qledger_support import U, E, settings


class QLedgerSessionLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchange_only_once_unit_switching_and_logout(self):
        from quollnet_mcp.qledger import auth

        connected = ContextVar("mcp_test_current_identity")
        first = SimpleNamespace(token="unique-ql-oauth-a", subject="alice", expires_at=int(time.time()) + 1500)
        second = SimpleNamespace(token="unique-ql-oauth-b", subject="bob", expires_at=int(time.time()) + 1500)
        connected.set(first)
        exchanges = []
        requests = []

        async def exchange(**kwargs):
            exchanges.append(kwargs)
            return kwargs["mcp_access_token"] + ":application"

        async def backend(method, path, *, access_token, **kwargs):
            requests.append((method, path, access_token))
            if path.endswith("/load"):
                uid = path.split("/")[-2]
                return {"unit": {"id": uid}, "token": access_token.split(":")[0] + ":" + uid}
            raise AssertionError("Unexpected QEntries call: " + path)

        fake_qauth = SimpleNamespace(settings=settings(), exchange_app_token=exchange)
        fake_ledger = SimpleNamespace(request=backend)
        with (
            patch.object(auth, "get_access_token", side_effect=lambda: connected.get(None)),
            patch.object(auth, "qauth_client", fake_qauth),
            patch.object(auth, "qledger_client", fake_ledger),
        ):
            self.assertEqual(await auth.application_token(), first.token + ":application")
            self.assertEqual(await auth.application_token(), first.token + ":application")
            self.assertEqual(len(exchanges), 1)
            self.assertEqual(await auth.unit_token(U), first.token + ":" + U)
            self.assertEqual(await auth.unit_token(U), first.token + ":" + U)
            self.assertEqual(len(requests), 1, "Unit should be loaded only once")
            self.assertEqual(await auth.unit_token(E), first.token + ":" + E)
            self.assertEqual(len(requests), 2)
            self.assertEqual(len(exchanges), 1, "Unit changes must not exchange MCP token")
            result = await auth.logout_qledger()
            payload = result.model_dump(by_alias=True, exclude_none=True)
            self.assertTrue(payload["isError"])
            challenge = payload["_meta"]["mcp/www_authenticate"][0]
            self.assertIn('error="invalid_token"', challenge)
            self.assertIn(
                'resource_metadata="https://mcp.quollnet.com/.well-known/oauth-protected-resource/qledger"',
                challenge,
            )
            # Challenge alone does not revoke the signed OAuth bearer. If ChatGPT
            # ignores the linking UI, reusing the old bearer can recreate the session.
            self.assertEqual(await auth.application_token(), first.token + ":application")
            self.assertEqual(len(exchanges), 2)
            connected.set(second)
            self.assertEqual(await auth.application_token(), second.token + ":application")
            self.assertEqual(len(exchanges), 3, "A new OAuth connection can authenticate")

    async def test_expiring_application_token_refreshes_using_qentries(self):
        from quollnet_mcp.qledger import auth

        first_jwt = jwt.encode({"exp": int(time.time()) + 20}, "test-only", algorithm="HS256")
        next_jwt = jwt.encode({"exp": int(time.time()) + 1800}, "test-only", algorithm="HS256")
        access = SimpleNamespace(token="unique-ql-oauth-refresh", subject="alice", expires_at=int(time.time()) + 1500)
        exchanges = []
        requests = []

        async def exchange(**kwargs):
            exchanges.append(kwargs)
            return first_jwt

        async def backend(method, path, *, access_token, **kwargs):
            requests.append((method, path, access_token))
            self.assertEqual((method, path), ("POST", "/api/auth/refresh"))
            return {"token": next_jwt, "token_type": "user"}

        with (
            patch.object(auth, "get_access_token", return_value=access),
            patch.object(auth, "qauth_client", SimpleNamespace(settings=settings(), exchange_app_token=exchange)),
            patch.object(auth, "qledger_client", SimpleNamespace(request=backend)),
        ):
            self.assertEqual(await auth.application_token(), first_jwt)
            self.assertEqual(await auth.application_token(), next_jwt)
            self.assertEqual(await auth.application_token(), next_jwt)
        self.assertEqual(len(exchanges), 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][2], first_jwt)


    async def test_challenge_does_not_change_shared_verifier_or_cashflowpot(self):
        from quollnet_mcp.auth import QAuthTokenVerifier
        from quollnet_mcp.qledger.server import build_qledger_server
        from quollnet_mcp.cashflowpot.server import build_cashflowpot_server

        self.assertEqual(
            type(build_qledger_server(settings())._tool_manager.get_tool("logout_qledger").fn).__name__,
            "function",
        )
        self.assertIsInstance(
            build_qledger_server(settings())._token_verifier,
            QAuthTokenVerifier,
        ) if hasattr(build_qledger_server(settings()), "_token_verifier") else None
        self.assertIsNotNone(build_cashflowpot_server(settings()))


if __name__ == "__main__":
    unittest.main()
