from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.qtools import get_qtool_development_guide


class GetQToolDevelopmentGuideTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_token_to_qapp(self) -> None:
        token = SimpleNamespace(
            token="bearer-token",
            subject="user-1",
            scopes=["qtools:read"],
        )
        expected = {
            "spec_version": 1,
            "spec_format": "text/markdown",
            "instructions": "# Quollnet qTools V2 Development Guide",
        }

        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=token,
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.get_qtool_development_guide",
                new=AsyncMock(return_value=expected),
            ) as get_guide,
        ):
            actual = await get_qtool_development_guide()

        self.assertIs(actual, expected)
        get_guide.assert_awaited_once_with(
            access_token="bearer-token",
        )

    async def test_requires_qtools_read_scope(self) -> None:
        token = SimpleNamespace(
            token="bearer-token",
            subject="user-1",
            scopes=["articles:read"],
        )

        with patch(
            "quollnet_mcp.tools.qtools.get_access_token",
            return_value=token,
        ):
            with self.assertRaisesRegex(ToolError, "qtools:read"):
                await get_qtool_development_guide()

    async def test_qapp_error_is_converted(self) -> None:
        token = SimpleNamespace(
            token="bearer-token",
            subject="user-1",
            scopes=["qtools:read"],
        )

        with (
            patch(
                "quollnet_mcp.tools.qtools.get_access_token",
                return_value=token,
            ),
            patch(
                "quollnet_mcp.tools.qtools.qapp_client.get_qtool_development_guide",
                new=AsyncMock(
                    side_effect=QAppClientError("qApp unavailable")
                ),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "qApp unavailable"):
                await get_qtool_development_guide()


if __name__ == "__main__":
    unittest.main()
