"""Dedicated MCP wire conversion with isolated HTTP and identity boundaries.

These tests exercise registered tools and QFlowClient serialization/error
handling. They do not contact a deployed service or exercise live OAuth.
"""

import copy
import json
import os
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import jsonschema
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

for _key in ("QAUTH_APP_ID", "QAUTH_PUBLIC_KEY", "QAPP_APP_ID", "CASHFLOWPOT_APP_ID"):
    os.environ.setdefault(_key, "test-wire-contract")

from quollnet_mcp.cashflowpot.server import register_cashflowpot_tools
from quollnet_mcp.dependencies import qauth_client, qflow_client
from quollnet_mcp.services.qauth_client import QAuthClientError


_MARKER = "WIRE-PRIVATE-SENTINEL"
_PRIVATE = {
    "token": f"{_MARKER}-token",
    "access_token": f"{_MARKER}-access",
    "created_by": f"{_MARKER}-user",
    "trace_id": f"{_MARKER}-trace",
}
_SCENARIO_ARGS = {"unit_id": "unit-1", "cashflow_id": "cf-1"}
_ACTIVITY_ARGS = {"unit_id": "unit-1", "activity_id": "a-1"}
_FACILITY_ARGS = {**_SCENARIO_ARGS, "facility_id": "f-1"}
_SOURCE = {
    "name": "Tender", "description": None, "contract_value": 1000,
    "inflow_curve_type": None,
    "activities": [{
        "name": "Manual Work", "activity_mode": "work",
        "distribution_type": "manual", "cost_schedule_json": [0, 100], "start": 0,
    }],
    "financing_facilities": [{
        "name": "Custom Debt", "type": "Custom Debt", "interest_rate": 0,
        "fees": 0, "limit": None, "draw_schedule": {"0": 100},
    }],
}


def _fixture_objects():
    activity = {
        "id": "a-1", "cashflow_id": "cf-1", "name": "Manual Work",
        "activity_type": "General", "activity_mode": "work",
        "distribution_type": "manual", "cost_schedule_json": [0, 100],
        "cost": 100, "duration": 2, "duration_units": "Periods", "start": 0,
        "advance": 0.1, "retention": 0.1, "release_retention_eop": 0.5,
        "dlp": 0, "duration_for_payment": 1, "work_in_excess": 0.1,
        "mobilization_period": 0, "subcontracted": 0.7, "skew": 0,
        "no_billing_period": 0, "is_deleted": False,
        "cash_flow_json": {"marginal_work": [0, 100]}, **_PRIVATE,
    }
    facility = {
        "id": "f-1", "name": "Custom Debt", "type": "Custom Debt",
        "draw_method": "scheduled", "repayment_method": "cashflow_sweep",
        "start": 0, "end": None, "limit": None, "revolving": False,
        "interest_rate": 0, "fees": 0, "sweep_priority": None,
        "draw_schedule": {"0": 100}, "repayment_schedule": {}, **_PRIVATE,
    }
    snapshot = {
        "id": "cf-1", "unit_id": "unit-1", "name": "Tender",
        "description": None, "contract_value": 1000,
        "advance": 0.1, "retention": 0.1, "release_retention_eop": 0.5,
        "dlp": 0, "duration_for_payment": 1, "wieb": 0.2,
        "interest_rate": 0.005, "use_independent_inflow_curve": False,
        "inflow_curve_type": None, "inflow_curve_skew": None,
        "activities": [activity], "financing_facilities": [facility],
        "summary": {
            "total_inflow": 1000, "work_cost": 100,
            "final_cash_balance": 900, "minimum_pre_financing_period": None,
            **_PRIVATE,
        },
        "workflow": [0, 100], "inflow": [0, 1000], "outflow": [0, 100],
        "netflow": [0, 900], "duration": 2,
        "pre_financing_balance": [0, 900], "facility_inflow": [100, 0],
        "facility_outflow": [0, 100], "facility_interest": [0, 0],
        "facility_fees": [0, 0], "funded_netflow": [100, 800],
        "unfunded_shortfall": [0, 0], "outflow_with_interest": [100, 900],
        "facility_rows": [{
            "id": "f-1", "name": "Custom Debt", "type": "Custom Debt",
            "draw_method": "scheduled", "repayment_method": "cashflow_sweep",
            "draw": [100, 0], "repayment": [0, 100], "interest": [0, 0],
            "fees": [0, 0], "outstanding": [100, 0], "available_limit": [None, None],
            **_PRIVATE,
        }],
        **_PRIVATE,
    }
    project = {
        "id": "unit-1", "name": "Project", "description": "Build",
        "cashflows": [snapshot], "roles": [{"name": "owner", **_PRIVATE}],
        "photo": f"{_MARKER}-photo", **_PRIVATE,
    }
    preset = {
        "key": "overdraft", "type": "Overdraft",
        "draw_method": "automatic_shortfall", "repayment_method": "cashflow_sweep",
        "revolving": True, "interest_rate": 0.005, "fees": 0,
        "interest_rate_basis": "per_period", "fees_basis": "fixed_amount",
        "default_fees_rate": 0.005 / 12,
        "default_fees_basis": "limit_or_scheduled_draw_total",
        "costs_note": "Editable illustrative simulation costs, not lender terms.",
        **_PRIVATE,
    }
    return activity, facility, snapshot, project, preset


@dataclass(frozen=True)
class _Case:
    name: str
    args: dict
    method: str
    path: str
    response: dict
    payload: dict | None = None
    scoped: bool = True


def _cases():
    activity, facility, snapshot, project, preset = _fixture_objects()

    def envelope(**data):
        return {**data, **_PRIVATE}

    def message(text):
        return envelope(message=text)

    generated_source = copy.deepcopy(_SOURCE)
    generated_source.pop("description")
    generated_source["financing_facilities"][0].pop("limit")
    portable_source = {**copy.deepcopy(_SOURCE), **_PRIVATE}
    portable_source["activities"] = [activity]
    portable_source["financing_facilities"] = [facility]
    project_args = {"unit_id": "unit-1"}
    activity_payload = copy.deepcopy(_SOURCE["activities"][0])
    facility_payload = {"name": "Custom Debt", "type": "Custom Debt", "interest_rate": 0, "fees": 0}
    document = {"format": "cashflowpot.cashflow", "version": 1, "cashflow": _SOURCE}
    cf_response = envelope(data=snapshot)
    return [
        _Case("list_cashflow_projects", {"page": 2, "per_page": 10}, "GET", "/projects", envelope(data=[project], pages=3), scoped=False),
        _Case("get_cashflow_project", project_args, "GET", "/project/unit-1", envelope(data=project)),
        _Case("create_cashflow_project", {"project": {"name": "Project", "description": "Build", "contract_value": 1000}}, "POST", "/new_project", envelope(data=project, message="Project created successfully"), {"name": "Project", "description": "Build", "contract_value": 1000}, False),
        _Case("update_cashflow_project", {**project_args, "project": {"description": "Revised"}}, "PUT", "/update_project/unit-1", envelope(data=project, message="Project updated successfully"), {"description": "Revised"}),
        _Case("delete_cashflow_project", project_args, "DELETE", "/delete_project/unit-1", message("Project deleted successfully")),
        _Case("restore_cashflow_project", project_args, "PUT", "/restore_project/unit-1", message("Project restored successfully"), scoped=False),
        _Case("hard_delete_cashflow_project", {**project_args, "confirm_permanent": True}, "DELETE", "/hard_delete_project/unit-1", message("Project hard deleted successfully"), scoped=False),
        _Case("get_cashflow", _SCENARIO_ARGS, "GET", "/cashflow/cf-1", cf_response),
        _Case("get_cashflow_results", {**_SCENARIO_ARGS, "detail": "full"}, "GET", "/cashflow/cf-1", cf_response),
        _Case("create_cashflow", {**project_args, "cashflow": _SOURCE}, "POST", "/project/unit-1/cashflows/import", envelope(data=snapshot, message="Cashflow imported successfully"), {"format": "cashflowpot.cashflow", "version": 1, "cashflow": generated_source}),
        _Case("update_cashflow", {**_SCENARIO_ARGS, "cashflow": {"description": None, "inflow_curve_type": None}}, "PUT", "/cashflow/cf-1", envelope(data=snapshot, message="Cashflow updated successfully"), {"description": None, "inflow_curve_type": None}),
        _Case("delete_cashflow", _SCENARIO_ARGS, "DELETE", "/cashflow/cf-1", message("Cashflow deleted successfully")),
        _Case("restore_cashflow", _SCENARIO_ARGS, "PUT", "/cashflow/cf-1/restore", message("Cashflow restored successfully")),
        _Case("hard_delete_cashflow", {**_SCENARIO_ARGS, "confirm_permanent": True}, "DELETE", "/cashflow/cf-1/hard", message("Cashflow hard deleted successfully")),
        _Case("export_cashflow_json", _SCENARIO_ARGS, "GET", "/cashflow/cf-1/export", envelope(format="cashflowpot.cashflow", version=1, cashflow=portable_source)),
        _Case("import_cashflow_json", {**project_args, "document": document}, "POST", "/project/unit-1/cashflows/import", envelope(data=snapshot, message="Cashflow imported successfully"), document),
        _Case("get_activity", _ACTIVITY_ARGS, "GET", "/activity/a-1", envelope(data=activity, message="Activity retrieved successfully")),
        _Case("get_activity_types", {}, "GET", "/activities/types", envelope(data={"general": {"type": "General", "name": "General", "distribution_type": "s_curve", "skew": 0, **_PRIVATE}}), scoped=False),
        _Case("list_deleted_activities", _SCENARIO_ARGS, "GET", "/deleted_activities/cf-1", envelope(data=[{**activity, "is_deleted": True}])),
        _Case("create_activity", {**_SCENARIO_ARGS, "activity": activity_payload}, "POST", "/new_activity/cf-1", envelope(data=activity, cashflow=snapshot, message="Activity created successfully"), activity_payload),
        _Case("update_activity", {**_ACTIVITY_ARGS, "activity": {"start": 4}}, "PUT", "/update_activity/a-1", envelope(data=activity, cashflow=snapshot, message="Activity updated successfully"), {"start": 4}),
        _Case("delete_activity", _ACTIVITY_ARGS, "DELETE", "/delete_activity/a-1", envelope(cashflow={**snapshot, "activities": []}, message="Activity deleted successfully")),
        _Case("restore_activity", _ACTIVITY_ARGS, "PUT", "/restore_activity/a-1", envelope(cashflow=snapshot, message="Activity restored successfully")),
        _Case("restore_activities", {**project_args, "activity_ids": ["a-1"]}, "PUT", "/restore_activities", envelope(cashflows=[snapshot], message="Activities restored successfully"), {"data": ["a-1"]}),
        _Case("hard_delete_activity", {**_ACTIVITY_ARGS, "confirm_permanent": True}, "DELETE", "/hard_delete_activity/a-1", envelope(cashflow={**snapshot, "activities": []}, message="Activity hard deleted successfully")),
        _Case("list_financing_facility_presets", {}, "GET", "/financing-facility-presets", envelope(data=[preset]), scoped=False),
        _Case("list_financing_facilities", _SCENARIO_ARGS, "GET", "/cashflow/cf-1/facilities", envelope(data=[facility])),
        _Case("get_financing_facility", _FACILITY_ARGS, "GET", "/cashflow/cf-1/facilities/f-1", envelope(data=facility)),
        _Case("add_financing_facility", {**_SCENARIO_ARGS, "facility": facility_payload}, "POST", "/cashflow/cf-1/facilities", envelope(facility=facility, cashflow=snapshot, message="Financing facility created successfully"), facility_payload),
        _Case("update_financing_facility", {**_FACILITY_ARGS, "facility": {"limit": None, "interest_rate": 0}}, "PUT", "/cashflow/cf-1/facilities/f-1", envelope(facility=facility, cashflow=snapshot, message="Financing facility updated successfully"), {"limit": None, "interest_rate": 0}),
        _Case("delete_financing_facility", _FACILITY_ARGS, "DELETE", "/cashflow/cf-1/facilities/f-1", envelope(cashflow={**snapshot, "financing_facilities": []}, message="Financing facility deleted successfully")),
        _Case("set_financing_facility_order", {**_SCENARIO_ARGS, "facility_ids": ["f-1"]}, "PUT", "/cashflow/cf-1/facilities/order", envelope(cashflow=snapshot, message="Financing facility order updated successfully"), {"facility_ids": ["f-1"]}),
        _Case("export_cashflow_excel", _SCENARIO_ARGS, "POST", "/cashflow/cf-1/excel-export", envelope(filename="Project-Tender.xlsx", download_url="https://cashflowpot.com/api/exports/cashflow/scoped-token.xlsx", expires_at="2026-10-20T12:10:00+00:00")),
    ]


class CashflowPotWireContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = MCPServer("cashflowpot-wire-contract-tests")
        register_cashflowpot_tools(self.server)
        self.advertised = {tool.name: tool for tool in await self.server.list_tools()}
        self.requests = []
        self.exchange = AsyncMock(return_value="application-secret-not-for-output")
        self.access = patch(
            "quollnet_mcp.cashflowpot.auth.get_access_token",
            return_value=SimpleNamespace(subject="user-1", token="mcp-secret-not-for-output"),
        )
        self.access.start()
        self.exchange_patch = patch.object(qauth_client, "exchange_app_token", self.exchange)
        self.exchange_patch.start()
        self.addCleanup(self.access.stop)
        self.addCleanup(self.exchange_patch.stop)

    async def _invoke(self, case, *, status=200, response=None):
        self.requests.clear()

        def handle(request):
            self.requests.append(request)
            return httpx.Response(status, json=case.response if response is None else response)

        async with httpx.AsyncClient(
            base_url="https://cashflowpot-backend.test", transport=httpx.MockTransport(handle),
        ) as client:
            with patch.object(qflow_client, "_client", client):
                return await self.server.call_tool(case.name, copy.deepcopy(case.args))

    async def _assert_success(self, case):
        result = await self._invoke(case)
        self.assertFalse(result.is_error)
        self.assertIsNotNone(result.structured_content)
        wire = json.dumps(result.model_dump(by_alias=True))
        for secret in (_MARKER, "application-secret-not-for-output", "mcp-secret-not-for-output"):
            self.assertNotIn(secret, wire)
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(request.method, case.method)
        self.assertEqual(request.url.path, case.path)
        self.assertEqual(request.headers["Authorization"], "Bearer application-secret-not-for-output")
        self.assertEqual(json.loads(request.content) if request.content else None, case.payload)
        if case.name == "list_cashflow_projects":
            self.assertEqual(dict(request.url.params), {"page": "2", "per_page": "10"})
        self.exchange.assert_awaited_once_with(
            mcp_access_token="mcp-secret-not-for-output",
            target_app_id=qauth_client.settings.cashflowpot_app_id,
            unit_id="unit-1" if case.scoped else None,
        )
        content = result.structured_content
        if case.name == "list_financing_facility_presets":
            self.assertEqual(content["data"][0]["default_fees_rate"], 0.005 / 12)
            self.assertEqual(content["data"][0]["default_fees_basis"], "limit_or_scheduled_draw_total")
        if case.name in {"get_cashflow", "create_cashflow", "update_cashflow", "import_cashflow_json"}:
            self.assertIsNone(content["data"]["description"])
        if case.name == "get_cashflow_project":
            self.assertIsNone(content["data"]["cashflows"][0]["description"])
            self.assertNotIn("activities", content["data"]["cashflows"][0])
        if case.name == "export_cashflow_json":
            self.assertIsNone(content["cashflow"]["description"])
            self.assertNotIn("id", content["cashflow"]["activities"][0])
        if case.name == "get_cashflow_results":
            self.assertEqual(content["properties"]["contract"]["contract_value"], 1000)
            self.assertEqual(content["properties"]["forecast"]["wieb"], 0.2)
            self.assertEqual(content["properties"]["units"]["interest_rate_basis"], "per_model_period")
        jsonschema.validate(result.structured_content, self.advertised[case.name].output_schema)

    async def test_exactly_all_33_advertised_tools_have_wire_cases(self):
        cases = _cases()
        self.assertEqual(len(cases), 33)
        self.assertEqual(len({case.name for case in cases}), 33)
        self.assertEqual({case.name for case in cases}, set(self.advertised))

    async def test_all_tools_map_unauthorized_backend_responses_to_static_errors(self):
        for status, expected in ((401, "Authentication expired or is invalid"), (403, "Access denied for this project or operation")):
            for case in _cases():
                with self.subTest(status=status, tool=case.name):
                    with self.assertRaises(ToolError) as raised:
                        await self._invoke(case, status=status, response={
                            "message": f"SQL diagnostic {_MARKER}", "error": f"Bearer {_MARKER}",
                            **_PRIVATE,
                        })
                    text = str(raised.exception)
                    self.assertIn(expected, text)
                    self.assertNotIn(_MARKER, text)
                    self.assertNotIn("SQL diagnostic", text)
                    self.assertEqual(len(self.requests), 1)

    async def test_all_tools_require_identity_before_backend_access(self):
        with patch("quollnet_mcp.cashflowpot.auth.get_access_token", return_value=None):
            for case in _cases():
                with self.subTest(tool=case.name):
                    with self.assertRaises(ToolError) as raised:
                        await self._invoke(case)
                    self.assertIn("Authentication is required", str(raised.exception))
                    self.assertEqual(self.requests, [])
        self.exchange.assert_not_awaited()

    async def test_identity_exchange_errors_do_not_echo_upstream_credentials(self):
        self.exchange.side_effect = QAuthClientError(f"Bearer {_MARKER}")
        with self.assertRaises(ToolError) as raised:
            await self._invoke(next(case for case in _cases() if case.name == "get_cashflow"))
        self.assertNotIn(_MARKER, str(raised.exception))
        self.assertEqual(self.requests, [])

    async def test_permanent_deletion_requires_true_before_any_external_call(self):
        for case in _cases():
            if not case.name.startswith("hard_delete_"):
                continue
            for confirmation in (None, False):
                args = {key: value for key, value in case.args.items() if key != "confirm_permanent"}
                if confirmation is not None:
                    args["confirm_permanent"] = confirmation
                guarded = _Case(case.name, args, case.method, case.path, case.response)
                with self.subTest(tool=case.name, confirmation=confirmation):
                    with self.assertRaises(ToolError) as raised:
                        await self._invoke(guarded)
                    self.assertIn("Permanent deletion cannot be undone", str(raised.exception))
                    self.assertEqual(self.requests, [])
        self.exchange.assert_not_awaited()

    async def test_unknown_properties_and_enum_typos_are_rejected_before_external_calls(self):
        invalid = [
            ("create_activity", {**_SCENARIO_ARGS, "activity": {"name": "Work", "cost": 100, "duration": 2, "activity_mode": "wrok"}}),
            ("create_activity", {**_SCENARIO_ARGS, "activity": {"name": "Work", "cost": 100, "duration": 2, "distribution_type": "liner"}}),
            ("update_cashflow", {**_SCENARIO_ARGS, "cashflow": {"inflow_curve_type": "curved"}}),
            ("add_financing_facility", {**_SCENARIO_ARGS, "facility": {"name": "Debt", "draw_method": "automatic"}}),
            ("add_financing_facility", {**_SCENARIO_ARGS, "facility": {"name": "Debt", "repayment_method": "sweep"}}),
            ("add_financing_facility", {**_SCENARIO_ARGS, "facility": {"name": "Debt", "interest_rtae": 0.01}}),
            ("update_financing_facility", {**_FACILITY_ARGS, "facility": {"fees_percent": 0.1}}),
            ("create_cashflow", {"unit_id": "unit-1", "cashflow": {"name": "Tender", "financing_facilities": [{"name": "Debt", "interest_rtae": 0.01}]}}),
        ]
        for name, args in invalid:
            case = _Case(name, args, "POST", "/must-not-be-called", {})
            with self.subTest(tool=name, args=args):
                with self.assertRaises(ToolError):
                    await self._invoke(case)
                self.assertEqual(self.requests, [])
        self.exchange.assert_not_awaited()

    async def test_unknown_success_messages_are_sanitized_in_both_wire_channels(self):
        case = next(case for case in _cases() if case.name == "delete_cashflow")
        result = await self._invoke(case, response={"message": f"Bearer {_MARKER}", **_PRIVATE})
        self.assertEqual(result.structured_content, {"message": "CashflowPot request completed."})
        self.assertNotIn(_MARKER, json.dumps(result.model_dump(by_alias=True)))
        jsonschema.validate(result.structured_content, self.advertised[case.name].output_schema)


def _wire_test(case):
    async def run(self):
        await self._assert_success(case)
    run.__name__ = f"test_wire_{case.name}"
    return run


for _case in _cases():
    setattr(CashflowPotWireContractTests, f"test_wire_{_case.name}", _wire_test(_case))


if __name__ == "__main__":
    unittest.main()
