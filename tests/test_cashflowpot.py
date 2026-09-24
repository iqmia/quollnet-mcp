from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.services.qauth_client import QAuthClientError
from quollnet_mcp.services.qflow_client import QFlowClientError
from quollnet_mcp.tools.cashflowpot import (
    CashflowActivityInput,
    CashflowInput,
    create_cashflow,
    list_cashflow_projects,
)


class CashflowPotToolTests(unittest.IsolatedAsyncioTestCase):
    def _token(self):
        return SimpleNamespace(
            token="mcp-bearer-token",
            subject="user-1",
            scopes=["mcp:connect"],
        )

    async def test_list_projects_exchanges_token_then_calls_qflow(self) -> None:
        expected = {
            "data": [
                {
                    "id": "unit-1",
                    "name": "Tower",
                    "cashflows": [{"id": "cf-1", "name": "Tender"}],
                }
            ],
            "pages": 1,
        }
        with (
            patch(
                "quollnet_mcp.tools.cashflowpot.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.cashflowpot.qauth_client.exchange_app_token",
                new=AsyncMock(return_value="cashflowpot-user-token"),
            ) as exchange,
            patch(
                "quollnet_mcp.tools.cashflowpot.qflow_client.list_projects",
                new=AsyncMock(return_value=expected),
            ) as projects,
        ):
            actual = await list_cashflow_projects(page=2, per_page=10)

        self.assertIs(actual, expected)
        exchange.assert_awaited_once_with(
            mcp_access_token="mcp-bearer-token",
            target_app_id="cashflowpot-test-app",
            unit_id=None,
        )
        projects.assert_awaited_once_with(
            access_token="cashflowpot-user-token",
            page=2,
            per_page=10,
        )

    async def test_create_cashflow_builds_portable_input_only(self) -> None:
        expected = {
            "message": "Cashflow imported successfully",
            "data": {"id": "cf-new", "name": "Tender scenario"},
        }
        cashflow = CashflowInput(
            name="Tender scenario",
            description="AI-assisted tender forecast",
            contract_value=1_250_000,
            advance=0.10,
            retention=0.10,
            release_retention_eop=0.50,
            dlp=12,
            duration_for_payment=1,
            interest_rate=0.005,
            wieb=0.20,
            activities=[
                CashflowActivityInput(
                    name="Structure",
                    activity_type="Structure",
                    cost=400_000,
                    duration=4,
                    start=1,
                    subcontracted=0.40,
                    skew=None,
                )
            ],
        )

        with (
            patch(
                "quollnet_mcp.tools.cashflowpot.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.cashflowpot.qauth_client.exchange_app_token",
                new=AsyncMock(return_value="cashflowpot-unit-token"),
            ) as exchange,
            patch(
                "quollnet_mcp.tools.cashflowpot.qflow_client.import_cashflow",
                new=AsyncMock(return_value=expected),
            ) as importer,
        ):
            actual = await create_cashflow(unit_id="unit-1", cashflow=cashflow)

        self.assertIs(actual, expected)
        exchange.assert_awaited_once_with(
            mcp_access_token="mcp-bearer-token",
            target_app_id="cashflowpot-test-app",
            unit_id="unit-1",
        )
        importer.assert_awaited_once()
        _, kwargs = importer.call_args
        self.assertEqual(kwargs["access_token"], "cashflowpot-unit-token")
        self.assertEqual(kwargs["unit_id"], "unit-1")

        payload = kwargs["payload"]
        self.assertEqual(payload["format"], "cashflowpot.cashflow")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["cashflow"]["name"], "Tender scenario")
        self.assertNotIn("id", payload["cashflow"])
        self.assertNotIn("workflow", payload["cashflow"])
        self.assertNotIn("inflow", payload["cashflow"])
        self.assertNotIn("outflow", payload["cashflow"])
        self.assertNotIn("skew", payload["cashflow"]["activities"][0])

    async def test_missing_authentication_is_rejected(self) -> None:
        with patch(
            "quollnet_mcp.tools.cashflowpot.get_access_token",
            return_value=None,
        ):
            with self.assertRaisesRegex(ToolError, "Authentication is required"):
                await list_cashflow_projects()

    async def test_qauth_exchange_error_is_tool_error(self) -> None:
        with (
            patch(
                "quollnet_mcp.tools.cashflowpot.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.cashflowpot.qauth_client.exchange_app_token",
                new=AsyncMock(
                    side_effect=QAuthClientError("Target application unavailable")
                ),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "Target application unavailable"):
                await list_cashflow_projects()

    async def test_qflow_permission_error_is_tool_error(self) -> None:
        cashflow = CashflowInput(name="Scenario")
        with (
            patch(
                "quollnet_mcp.tools.cashflowpot.get_access_token",
                return_value=self._token(),
            ),
            patch(
                "quollnet_mcp.tools.cashflowpot.qauth_client.exchange_app_token",
                new=AsyncMock(return_value="cashflowpot-user-token"),
            ),
            patch(
                "quollnet_mcp.tools.cashflowpot.qflow_client.import_cashflow",
                new=AsyncMock(
                    side_effect=QFlowClientError(
                        "q_flow returned HTTP 403: Missing required project permission"
                    )
                ),
            ),
        ):
            with self.assertRaisesRegex(ToolError, "HTTP 403"):
                await create_cashflow(unit_id="unit-1", cashflow=cashflow)

    def test_activity_advance_plus_retention_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            CashflowActivityInput(
                name="Invalid",
                cost=100,
                duration=1,
                advance=0.8,
                retention=0.3,
            )


if __name__ == "__main__":
    unittest.main()
