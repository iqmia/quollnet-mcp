import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.cashflowpot.models import (
    ActivityInput,
    ActivityUpdate,
    CashflowUpdate,
    FinancingFacilityUpdate,
)
from quollnet_mcp.cashflowpot.tools.activities import create_activity, update_activity
from quollnet_mcp.cashflowpot.tools.cashflows import (
    export_cashflow_json,
    get_cashflow_results,
    update_cashflow,
)
from quollnet_mcp.cashflowpot.tools.exports import export_cashflow_excel
from quollnet_mcp.cashflowpot.tools.facilities import update_financing_facility


EXPECTED_TOOLS = {
    "list_cashflow_projects",
    "get_cashflow_project",
    "create_cashflow_project",
    "update_cashflow_project",
    "delete_cashflow_project",
    "restore_cashflow_project",
    "hard_delete_cashflow_project",
    "get_cashflow",
    "get_cashflow_results",
    "create_cashflow",
    "update_cashflow",
    "delete_cashflow",
    "restore_cashflow",
    "hard_delete_cashflow",
    "export_cashflow_json",
    "import_cashflow_json",
    "get_activity",
    "get_activity_types",
    "list_deleted_activities",
    "create_activity",
    "update_activity",
    "delete_activity",
    "restore_activity",
    "restore_activities",
    "hard_delete_activity",
    "list_financing_facility_presets",
    "list_financing_facilities",
    "get_financing_facility",
    "add_financing_facility",
    "update_financing_facility",
    "delete_financing_facility",
    "set_financing_facility_order",
    "export_cashflow_excel",
}


class CashflowPotRegistrationTests(unittest.TestCase):
    def test_dedicated_server_registers_exact_approved_surface(self) -> None:
        from combined_app import cashflowpot_mcp

        names = {tool.name for tool in cashflowpot_mcp._tool_manager._tools.values()}
        self.assertEqual(names, EXPECTED_TOOLS)

    def test_existing_central_mcp_is_not_expanded(self) -> None:
        import app as legacy

        names = {tool.name for tool in legacy.mcp._tool_manager._tools.values()}
        self.assertIn("list_cashflow_projects", names)
        self.assertIn("create_cashflow", names)
        self.assertNotIn("get_cashflow_project", names)
        self.assertNotIn("export_cashflow_excel", names)
        self.assertNotIn("add_financing_facility", names)

    def test_read_and_destructive_annotations_are_set(self) -> None:
        from combined_app import cashflowpot_mcp

        tools = {tool.name: tool for tool in cashflowpot_mcp._tool_manager._tools.values()}
        self.assertTrue(tools["get_cashflow"].annotations.read_only_hint)
        self.assertTrue(tools["export_cashflow_excel"].annotations.read_only_hint)
        self.assertTrue(tools["delete_activity"].annotations.destructive_hint)
        self.assertTrue(tools["hard_delete_cashflow_project"].annotations.destructive_hint)
        self.assertFalse(tools["update_cashflow"].annotations.destructive_hint)


class CashflowPotActivityModelTests(unittest.TestCase):
    def test_manual_and_scheduled_cost_preserve_zero_based_source(self) -> None:
        manual = ActivityInput(
            name="Manual Work",
            activity_mode="work",
            distribution_type="manual",
            cost_schedule_json=[100, 200],
            start=0,
        )
        scheduled = ActivityInput(
            name="LC Material",
            activity_mode="scheduled_cost",
            distribution_type="manual",
            cost_schedule_json=[5000],
            start=0,
        )
        self.assertEqual(manual.start, 0)
        self.assertEqual(scheduled.start, 0)
        self.assertEqual(manual.cost_schedule_json[0], 100)
        self.assertEqual(scheduled.cost_schedule_json[0], 5000)

    def test_activity_update_can_change_one_field_only(self) -> None:
        update = ActivityUpdate(start=4)
        self.assertEqual(update.model_dump(exclude_unset=True), {"start": 4})


class CashflowPotToolForwardingTests(unittest.IsolatedAsyncioTestCase):
    async def test_activity_source_is_forwarded_without_calculation(self) -> None:
        activity = ActivityInput(
            name="Scheduled Mobilization",
            activity_mode="scheduled_cost",
            distribution_type="manual",
            cost_schedule_json=[25000, 0, 10000],
            start=0,
        )
        expected = {"cashflow": {"id": "cf-1"}}
        with (
            patch(
                "quollnet_mcp.cashflowpot.tools.activities.cashflowpot_token",
                new=AsyncMock(return_value="unit-token"),
            ),
            patch(
                "quollnet_mcp.cashflowpot.tools.activities.qflow_client.create_activity",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await create_activity("unit-1", "cf-1", activity)

        self.assertIs(result, expected)
        payload = call.await_args.kwargs["payload"]
        self.assertEqual(payload["start"], 0)
        self.assertEqual(payload["cost_schedule_json"], [25000.0, 0.0, 10000.0])
        self.assertNotIn("cash_flow_json", payload)

    async def test_results_use_qflow_serialized_financing_keys(self) -> None:
        snapshot = {
            "id": "cf-1",
            "unit_id": "unit-1",
            "name": "Tender",
            "summary": {"peak_pre_financing_need": 125000},
            "workflow": [10, 20],
            "inflow": [0, 50],
            "outflow": [25, 30],
            "netflow": [-25, 20],
            "pre_financing_balance": [-25, -5],
            "facility_rows": [{"id": "fac-1"}],
            "facility_inflow": [25, 0],
            "facility_outflow": [0, 10],
            "facility_interest": [0, 1],
            "facility_fees": [2, 0],
            "funded_netflow": [0, 9],
            "unfunded_shortfall": [0, 0],
            "outflow_with_interest": [0, 9],
        }
        with patch(
            "quollnet_mcp.cashflowpot.tools.cashflows.get_cashflow",
            new=AsyncMock(return_value={"data": snapshot}),
        ):
            result = await get_cashflow_results("unit-1", "cf-1")

        for key in (
            "facility_inflow",
            "facility_outflow",
            "funded_netflow",
            "facility_interest",
            "facility_fees",
        ):
            self.assertEqual(result[key], snapshot[key])
        self.assertNotIn("facility_draws", result)
        self.assertNotIn("principal_repayments", result)

    async def test_cashflow_update_preserves_explicit_null_to_clear_curve(self) -> None:
        expected = {"data": {"id": "cf-1", "inflow_curve_type": None}}
        with (
            patch(
                "quollnet_mcp.cashflowpot.tools.cashflows.cashflowpot_token",
                new=AsyncMock(return_value="unit-token"),
            ),
            patch(
                "quollnet_mcp.cashflowpot.tools.cashflows.qflow_client.update_cashflow",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await update_cashflow(
                "unit-1", "cf-1", CashflowUpdate(inflow_curve_type=None)
            )

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            access_token="unit-token",
            cashflow_id="cf-1",
            payload={"inflow_curve_type": None},
        )

    async def test_activity_update_preserves_explicit_null(self) -> None:
        expected = {"cashflow": {"id": "cf-1"}}
        with (
            patch(
                "quollnet_mcp.cashflowpot.tools.activities.cashflowpot_token",
                new=AsyncMock(return_value="unit-token"),
            ),
            patch(
                "quollnet_mcp.cashflowpot.tools.activities.qflow_client.update_activity",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await update_activity(
                "unit-1", "a-1", ActivityUpdate(cost_schedule_json=None)
            )

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            access_token="unit-token",
            activity_id="a-1",
            payload={"cost_schedule_json": None},
        )

    async def test_facility_update_uses_atomic_backend_operation(self) -> None:
        expected = {"facility": {"id": "fac-1", "limit": 250000}}
        with (
            patch(
                "quollnet_mcp.cashflowpot.tools.facilities.cashflowpot_token",
                new=AsyncMock(return_value="unit-token"),
            ),
            patch(
                "quollnet_mcp.cashflowpot.tools.facilities.qflow_client.update_financing_facility",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await update_financing_facility(
                "unit-1",
                "cf-1",
                "fac-1",
                FinancingFacilityUpdate(limit=250000),
            )

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            access_token="unit-token",
            cashflow_id="cf-1",
            facility_id="fac-1",
            payload={"limit": 250000.0},
        )

    async def test_facility_update_preserves_explicit_null_for_unlimited_limit(self) -> None:
        expected = {"facility": {"id": "fac-1", "limit": None}}
        with (
            patch(
                "quollnet_mcp.cashflowpot.tools.facilities.cashflowpot_token",
                new=AsyncMock(return_value="unit-token"),
            ),
            patch(
                "quollnet_mcp.cashflowpot.tools.facilities.qflow_client.update_financing_facility",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await update_financing_facility(
                "unit-1",
                "cf-1",
                "fac-1",
                FinancingFacilityUpdate(limit=None),
            )

        self.assertIs(result, expected)
        call.assert_awaited_once_with(
            access_token="unit-token",
            cashflow_id="cf-1",
            facility_id="fac-1",
            payload={"limit": None},
        )

    async def test_portable_json_is_backend_returned_not_rebuilt(self) -> None:
        expected = {
            "format": "cashflowpot.cashflow",
            "version": 1,
            "cashflow": {"name": "Tender", "activities": []},
        }
        with (
            patch(
                "quollnet_mcp.cashflowpot.tools.cashflows.cashflowpot_token",
                new=AsyncMock(return_value="unit-token"),
            ),
            patch(
                "quollnet_mcp.cashflowpot.tools.cashflows.qflow_client.export_cashflow",
                new=AsyncMock(return_value=expected),
            ),
        ):
            result = await export_cashflow_json("unit-1", "cf-1")
        self.assertIs(result, expected)

    async def test_excel_tool_returns_signed_metadata_without_fetching_file(self) -> None:
        expected = {
            "filename": "Project - Scenario.xlsx",
            "download_url": "https://cashflowpot.com/api/exports/cashflow/token.xlsx",
            "expires_at": "2026-10-17T00:20:00+00:00",
        }
        with (
            patch(
                "quollnet_mcp.cashflowpot.tools.exports.cashflowpot_token",
                new=AsyncMock(return_value="unit-token"),
            ),
            patch(
                "quollnet_mcp.cashflowpot.tools.exports.qflow_client.request_excel_export",
                new=AsyncMock(return_value=expected),
            ) as call,
        ):
            result = await export_cashflow_excel("unit-1", "cf-1")

        call.assert_awaited_once_with(access_token="unit-token", cashflow_id="cf-1")
        self.assertEqual(result["filename"], expected["filename"])
        self.assertEqual(result["download_url"], expected["download_url"])
        self.assertIn("not stored", result["message"])


if __name__ == "__main__":
    unittest.main()
