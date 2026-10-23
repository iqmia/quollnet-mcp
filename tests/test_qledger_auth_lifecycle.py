"""QLedger-only session lifecycle; deliberately no CashflowPot implementation changes."""

import time
import unittest
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from tests.qledger_support import U, E, settings


class QLedgerSessionLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchange_once_unit_switching_and_separate_profiles(self):
        from quollnet_mcp.qledger import auth

        connected = ContextVar("mcp_test_current_identity")
        first = SimpleNamespace(token="unique-ql-oauth-a", subject="alice", claims={"name": "Alice", "email": "alice@example.test"}, expires_at=int(time.time()) + 1500)
        second = SimpleNamespace(token="unique-ql-oauth-b", subject="bob", claims={"name": "Bob", "email": "bob@example.test"}, expires_at=int(time.time()) + 1500)
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
            self.assertEqual(
                auth.get_qledger_profile(),
                {"id": "alice", "name": "Alice", "email": "alice@example.test"},
            )
            self.assertEqual(len(exchanges), 1, "Profile must not trigger QAuth exchange")
            connected.set(second)
            self.assertEqual(
                auth.get_qledger_profile(),
                {"id": "bob", "name": "Bob", "email": "bob@example.test"},
            )
            self.assertEqual(await auth.application_token(), second.token + ":application")
            self.assertEqual(len(exchanges), 2, "Another OAuth connection authenticates independently")
            connected.set(first)
            self.assertEqual(await auth.application_token(), first.token + ":application")
            self.assertEqual(len(exchanges), 2, "Switching back reuses the original account cache")


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


    async def test_profile_validation_without_display_data_and_no_user_selector(self):
        from quollnet_mcp.qledger import auth
        from quollnet_mcp.qledger.server import build_qledger_server
        from quollnet_mcp.cashflowpot.server import build_cashflowpot_server

        bearer = SimpleNamespace(token="unique-profile-1", subject="stable-id", claims={}, expires_at=int(time.time()) + 100)
        with (
            patch.object(auth, "get_access_token", return_value=bearer),
            patch.object(auth, "qauth_client", SimpleNamespace(settings=settings())),
        ):
            self.assertEqual(auth.get_qledger_profile(), {"id": "stable-id"})

        server = build_qledger_server(settings())
        tool = next(t for t in await server.list_tools() if t.name == "get_qledger_profile")
        self.assertEqual(tool.input_schema.get("properties"), {})
        self.assertIs(tool.meta["openai/profile"], True)
        self.assertTrue(tool.annotations.read_only_hint)
        self.assertIsNotNone(build_cashflowpot_server(settings()))


if __name__ == "__main__":
    unittest.main()
