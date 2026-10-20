"""Dedicated CashflowPot MCP follows the Flutter client's q_flow token handoff."""

import json
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import jwt

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.cashflowpot.auth import cashflowpot_token
from quollnet_mcp.cashflowpot import token_store
from quollnet_mcp.services.qflow_client import QFlowClient


APP_ID = "cashflowpot-test-app"


def qauth_token(user_id: str, *, unit_id: str | None = None) -> str:
    claims = {
        "user_id": user_id,
        "client_app_id": APP_ID,
        "aud": APP_ID,
        "exp": int(time.time()) + 3600,
    }
    if unit_id:
        claims["unit_id"] = unit_id
    return jwt.encode(claims, "test-only-key", algorithm="HS256")


def oauth_token(user_id: str, suffix: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        subject=user_id,
        token=f"oauth-for-{user_id}-{suffix}",
        expires_at=int(time.time()) + 3600,
    )


class TokenReuseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        token_store._tokens.clear()
        token_store._current_connection.set(None)

    async def _make_client(self, handler):
        client = QFlowClient()
        client._client = httpx.AsyncClient(
            base_url="https://cashflowpot.invalid/api/",
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(client._client.aclose)
        return client

    async def test_first_exchange_only_and_reuse_unit_and_refreshed_tokens(self):
        user = oauth_token("user-one")
        first = qauth_token("user-one")
        unit = qauth_token("user-one", unit_id="project-one")
        refreshed = qauth_token("user-one", unit_id="project-one")
        # Refreshed token has a distinct signature / payload.
        refreshed = jwt.encode(
            {**jwt.decode(refreshed, options={"verify_signature": False}),
             "iat": int(time.time()) + 1}, "test-only-key", algorithm="HS256"
        )
        seen = []

        def handler(request):
            seen.append(request.headers["Authorization"])
            if len(seen) == 1:
                return httpx.Response(
                    200, headers={"Authorization": f"Bearer {unit}"},
                    json={"data": {"id": "project-one"}, "token": unit},
                )
            if len(seen) == 2:
                return httpx.Response(
                    200, headers={"Authorization": f"Bearer {refreshed}"},
                    json={"data": {"id": "scenario-one"}, "token": refreshed},
                )
            return httpx.Response(200, json={"data": {"id": "scenario-one"}})

        client = await self._make_client(handler)
        with (
            patch("quollnet_mcp.cashflowpot.auth.get_access_token", return_value=user),
            patch("quollnet_mcp.cashflowpot.auth.qauth_client.exchange_app_token",
                  new=AsyncMock(return_value=first)) as exchange,
        ):
            initial = await cashflowpot_token("project-one")
            self.assertEqual(initial, first)
            response = await client.get_project(
                access_token=initial, unit_id="project-one",
            )
            self.assertNotIn("token", response)

            current = await cashflowpot_token("project-one")
            self.assertEqual(current, unit)
            response = await client.get_cashflow(
                access_token=current, cashflow_id="scenario-one",
            )
            self.assertNotIn("token", response)

            current = await cashflowpot_token("project-one")
            self.assertEqual(current, refreshed)
            await client.get_cashflow(
                access_token=current, cashflow_id="scenario-one",
            )

            exchange.assert_awaited_once_with(
                mcp_access_token=user.token,
                target_app_id=APP_ID,
                unit_id=None,
            )
            self.assertEqual(seen, [
                f"Bearer {first}", f"Bearer {unit}", f"Bearer {refreshed}",
            ])

    async def test_different_users_and_oauth_connections_do_not_share_tokens(self):
        with (
            patch("quollnet_mcp.cashflowpot.auth.get_access_token") as current,
            patch("quollnet_mcp.cashflowpot.auth.qauth_client.exchange_app_token",
                  new=AsyncMock(side_effect=[
                      qauth_token("user-one"),
                      qauth_token("user-two"),
                      qauth_token("user-one", unit_id="project-two"),
                  ])) as exchange,
        ):
            current.return_value = oauth_token("user-one", "connection-a")
            first = await cashflowpot_token()
            current.return_value = oauth_token("user-two", "connection-b")
            second = await cashflowpot_token()
            current.return_value = oauth_token("user-one", "connection-c")
            third = await cashflowpot_token()
            current.return_value = oauth_token("user-one", "connection-a")
            self.assertEqual(await cashflowpot_token(), first)

            self.assertNotEqual(first, second)
            self.assertNotEqual(first, third)
            self.assertEqual(exchange.await_count, 3)

    async def test_root_body_token_is_used_if_header_absent(self):
        user = oauth_token("user-one")
        original = qauth_token("user-one")
        updated = qauth_token("user-one", unit_id="project-two")
        client = await self._make_client(
            lambda _: httpx.Response(200, json={"token": updated, "message": "ok"})
        )
        with (
            patch("quollnet_mcp.cashflowpot.auth.get_access_token", return_value=user),
            patch("quollnet_mcp.cashflowpot.auth.qauth_client.exchange_app_token",
                  new=AsyncMock(return_value=original)),
        ):
            sent = await cashflowpot_token()
            result = await client.list_projects(access_token=sent)
            self.assertEqual(result, {"message": "ok"})
            self.assertEqual(await cashflowpot_token(), updated)

    async def test_other_user_token_is_never_cached(self):
        user = oauth_token("user-one")
        original = qauth_token("user-one")
        other = qauth_token("user-two", unit_id="project-one")
        with (
            patch("quollnet_mcp.cashflowpot.auth.get_access_token", return_value=user),
            patch("quollnet_mcp.cashflowpot.auth.qauth_client.exchange_app_token",
                  new=AsyncMock(return_value=original)),
        ):
            current = await cashflowpot_token()
            self.assertFalse(token_store.accept_cashflowpot_token_from_qflow(
                sent_token=current, replacement_token=other,
            ))
            self.assertEqual(await cashflowpot_token(), original)

    async def test_late_response_cannot_overwrite_newer_unit_token(self):
        user = oauth_token("user-one")
        original = qauth_token("user-one")
        a = qauth_token("user-one", unit_id="project-a")
        b = qauth_token("user-one", unit_id="project-b")
        with (
            patch("quollnet_mcp.cashflowpot.auth.get_access_token", return_value=user),
            patch("quollnet_mcp.cashflowpot.auth.qauth_client.exchange_app_token",
                  new=AsyncMock(return_value=original)),
        ):
            used = await cashflowpot_token()
            self.assertTrue(token_store.accept_cashflowpot_token_from_qflow(
                sent_token=used, replacement_token=a,
            ))
            self.assertFalse(token_store.accept_cashflowpot_token_from_qflow(
                sent_token=used, replacement_token=b,
            ))
            self.assertEqual(await cashflowpot_token(), a)

    async def test_invalid_token_does_not_enter_cache_or_tool_results(self):
        user = oauth_token("user-one")
        initial = qauth_token("user-one")
        client = await self._make_client(
            lambda _: httpx.Response(200, json={"token": "not-a-jwt", "message": "ok"})
        )
        with (
            patch("quollnet_mcp.cashflowpot.auth.get_access_token", return_value=user),
            patch("quollnet_mcp.cashflowpot.auth.qauth_client.exchange_app_token",
                  new=AsyncMock(return_value=initial)),
        ):
            used = await cashflowpot_token()
            self.assertEqual(await client.list_projects(access_token=used),
                             {"message": "ok"})
            self.assertEqual(await cashflowpot_token(), initial)


if __name__ == "__main__":
    unittest.main()
