from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "qauth-main-test-app")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.services.qauth_client import QAuthClientError
from quollnet_mcp.tools.qapp_auth import get_current_user, qapp_user_token


class QAppUserTokenTests(unittest.IsolatedAsyncioTestCase):
    async def test_exchanges_mcp_token_into_qapp(self) -> None:
        access_token = SimpleNamespace(
            token="mcp-token",
            subject="user-1",
            claims={"user_id": "user-1"},
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
            target_app_id="qapp-test-app",
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
            claims={"user_id": "user-1"},
        )

        with (
            patch(
                "quollnet_mcp.tools.qapp_auth.get_access_token",
                return_value=access_token,
            ),
            patch(
                "quollnet_mcp.tools.qapp_auth.qauth_client.exchange_app_token",
                new=AsyncMock(
                    side_effect=QAuthClientError("target app denied exchange")
                ),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "target app denied exchange"):
                await qapp_user_token()


class GetCurrentUserTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_identity_directly_from_mcp_claims(self) -> None:
        access_token = SimpleNamespace(
            token="mcp-token",
            subject="user-1",
            claims={
                "user_id": "user-1",
                "name": "Karl Saad",
                "email": "karl@example.com",
                "app_roles": "user",
                "roles": "user",
                "is_active": True,
            },
        )

        with patch(
            "quollnet_mcp.tools.qapp_auth.get_access_token",
            return_value=access_token,
        ):
            actual = await get_current_user()

        self.assertEqual(
            actual,
            {
                "data": {
                    "user_id": "user-1",
                    "name": "Karl Saad",
                    "email": "karl@example.com",
                    "app_roles": "user",
                    "roles": "user",
                    "is_active": True,
                }
            },
        )

    async def test_requires_authenticated_identity(self) -> None:
        with patch(
            "quollnet_mcp.tools.qapp_auth.get_access_token",
            return_value=None,
        ):
            with self.assertRaisesRegex(ToolError, "Authentication is required"):
                await get_current_user()


if __name__ == "__main__":
    unittest.main()
