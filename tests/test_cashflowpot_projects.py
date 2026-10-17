import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.cashflowpot.tools.projects import (
    delete_cashflow_project,
    hard_delete_cashflow_project,
    restore_cashflow_project,
)


class CashflowPotProjectTokenScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_uses_unit_token_while_restore_and_hard_delete_use_app_token(self) -> None:
        with (
            patch(
                "quollnet_mcp.cashflowpot.tools.projects.cashflowpot_token",
                new=AsyncMock(side_effect=["unit-token", "app-token", "app-token"]),
            ) as token,
            patch(
                "quollnet_mcp.cashflowpot.tools.projects.qflow_client.delete_project",
                new=AsyncMock(return_value={"message": "deleted"}),
            ) as delete_call,
            patch(
                "quollnet_mcp.cashflowpot.tools.projects.qflow_client.restore_project",
                new=AsyncMock(return_value={"message": "restored"}),
            ) as restore_call,
            patch(
                "quollnet_mcp.cashflowpot.tools.projects.qflow_client.hard_delete_project",
                new=AsyncMock(return_value={"message": "hard deleted"}),
            ) as hard_delete_call,
        ):
            await delete_cashflow_project("unit-1")
            await restore_cashflow_project("unit-1")
            await hard_delete_cashflow_project("unit-1")

        self.assertEqual(
            token.await_args_list,
            [
                unittest.mock.call("unit-1"),
                unittest.mock.call(),
                unittest.mock.call(),
            ],
        )
        delete_call.assert_awaited_once_with(
            access_token="unit-token", unit_id="unit-1"
        )
        restore_call.assert_awaited_once_with(
            access_token="app-token", unit_id="unit-1"
        )
        hard_delete_call.assert_awaited_once_with(
            access_token="app-token", unit_id="unit-1"
        )


if __name__ == "__main__":
    unittest.main()
