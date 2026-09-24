from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.services.qauth_client import QAuthClientError
from quollnet_mcp.tools.qapp_auth import (
    get_current_user,
    qapp_user_identity,
    qapp_user_token,
)


class QAppUserTokenTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchanges_mcp_token_back_into_qapp(self) -> None:
        access_token = SimpleNamespace(
            token="mcp-token",
            subject="user-1",
        )

        with (
            patch(
                "quollnet_mcp.tools.qapp_auth.get_access_token",
                return_value=access_token,
            ),
            patch(
                "quollnet_mcp.tools.qapp_auth.qauth_client.exchange_app_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ) as exchange,
        ):
            token = await qapp_user_token()

        self.assertEqual(token, "qapp-user-token")
        exchange.assert_awaited_once_with(
            mcp_access_token="mcp-token",
            target_app_id="test-app-id",
        )

    async def test_requires_authenticated_mcp_identity(self) -> None:
        with patch(
            "quollnet_mcp.tools.qapp_auth.get_access_token",
            return_value=None,
        ):
            with self.assertRaisesRegex(ToolError, "Authentication is required"):
                await qapp_user_token()

    async def test_exchange_error_is_exposed_as_tool_error(self) -> None:
        access_token = SimpleNamespace(
            token="mcp-token",
            subject="user-1",
        )

        with (
            patch(
                "quollnet_mcp.tools.qapp_auth.get_access_token",
                return_value=access_token,
            ),
            patch(
                "quollnet_mcp.tools.qapp_auth.qauth_client.exchange_app_token",
                new=AsyncMock(
                    side_effect=QAuthClientError("self-exchange denied")
                ),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "self-exchange denied"):
                await qapp_user_token()


class QAppUserIdentityTests(unittest.TestCase):
    def test_returns_connected_qapp_identity(self) -> None:
        claims = {
            "user_id": "user-1",
            "client_app_id": "test-app-id",
            "name": "Karl Saad",
            "email": "karl@example.com",
            "app_roles": "admin",
            "roles": "user",
            "is_active": True,
        }

        with patch(
            "quollnet_mcp.tools.qapp_auth.jwt.decode",
            return_value=claims,
        ) as decode:
            identity = qapp_user_identity("qapp-user-token")

        self.assertEqual(identity, {
            "user_id": "user-1",
            "name": "Karl Saad",
            "email": "karl@example.com",
            "app_roles": "admin",
            "roles": "user",
            "is_active": True,
        })
        decode.assert_called_once_with(
            "qapp-user-token",
            "test-public-key",
            algorithms=["RS256"],
            audience="test-app-id",
            options={
                "require": [
                    "exp",
                    "aud",
                    "user_id",
                    "client_app_id",
                ]
            },
        )

    def test_rejects_wrong_qapp_application(self) -> None:
        with patch(
            "quollnet_mcp.tools.qapp_auth.jwt.decode",
            return_value={
                "user_id": "user-1",
                "client_app_id": "another-app",
            },
        ):
            with self.assertRaisesRegex(ToolError, "wrong application"):
                qapp_user_identity("qapp-user-token")


class GetCurrentUserTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_identity_from_exchanged_qapp_token(self) -> None:
        expected = {
            "user_id": "user-1",
            "name": "Karl Saad",
            "email": "karl@example.com",
            "app_roles": "admin",
            "roles": "user",
            "is_active": True,
        }

        with (
            patch(
                "quollnet_mcp.tools.qapp_auth.qapp_user_token",
                new=AsyncMock(return_value="qapp-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.qapp_auth.qapp_user_identity",
                return_value=expected,
            ),
        ):
            actual = await get_current_user()

        self.assertEqual(actual, {"data": expected})


if __name__ == "__main__":
    unittest.main()
