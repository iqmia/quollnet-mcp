"""Public schema and credential-boundary checks for backend tool responses."""

import json
import unittest

import jsonschema
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import TypeAdapter

from quollnet_mcp.cashflowpot.responses import (
    ActivityListResponse,
    ActivityResponse,
    ActivityTypesResponse,
    CashflowResponse,
    ExcelResponse,
    FacilityListResponse,
    FacilityPresetsResponse,
    FacilityResponse,
    MessageResponse,
    PortableResponse,
    ProjectListResponse,
    ProjectResponse,
    ResultsResponse,
    project_response,
)


class CashflowPotResponseBoundaryTests(unittest.TestCase):
    def test_accepted_legacy_integer_schedule_keys_round_trip(self) -> None:
        from quollnet_mcp.cashflowpot.models import FinancingFacilityInput

        for key in ("01", "+1", " 1 ", "1_0", "-0"):
            with self.subTest(period=key):
                source = FinancingFacilityInput(
                    name="Legacy", draw_schedule={key: 100},
                ).model_dump(exclude_none=True)
                result = project_response({"data": source}, FacilityResponse)
                self.assertEqual(result["data"]["draw_schedule"], {key: 100})
                jsonschema.validate(result, TypeAdapter(FacilityResponse).json_schema())

    def test_nested_credentials_and_orm_metadata_are_removed(self) -> None:
        source = {
            "token": "TOP-SECRET",
            "data": {
                "id": "cf-1",
                "unit_id": "unit-1",
                "name": "Tender",
                "created_by": "PRIVATE-USER",
                "created_at": "PRIVATE-TIME",
                "activities": [{
                    "id": "a-1", "cashflow_id": "cf-1", "name": "Work",
                    "cost": 123.45, "cash_flow_json": {"marginal_work": [1]},
                    "updated_by": "PRIVATE-USER", "token": "ACTIVITY-SECRET",
                }],
                "financing_facilities": [{
                    "id": "f-1", "name": "Overdraft", "type": "Other",
                    "limit": None, "draw_schedule": {"0": 100},
                    "access_token": "FACILITY-SECRET", "private_notes": "PRIVATE",
                }],
                "summary": {
                    "final_cash_balance": 5.5,
                    "minimum_pre_financing_period": None,
                    "refresh_token": "SUMMARY-SECRET",
                },
                "facility_rows": [{
                    "id": "f-1", "draw": [100], "available_limit": [None],
                    "authorization": "ROW-SECRET",
                }],
                "workflow": [0, 123.45],
            },
        }

        result = project_response(source, CashflowResponse)

        self.assertEqual(result["data"]["id"], "cf-1")
        self.assertEqual(result["data"]["activities"], [{
            "id": "a-1", "cashflow_id": "cf-1", "name": "Work", "cost": 123.45,
        }])
        self.assertEqual(result["data"]["summary"], {
            "final_cash_balance": 5.5, "minimum_pre_financing_period": None,
        })
        self.assertEqual(result["data"]["financing_facilities"][0]["limit"], None)
        self.assertEqual(result["data"]["workflow"], [0, 123.45])
        self.assertEqual(result["data"]["facility_rows"][0]["available_limit"], [None])
        encoded = json.dumps(result)
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("PRIVATE", encoded)
        self.assertNotIn("cash_flow_json", encoded)
        self.assertIn("token", source)

    def test_project_lists_keep_only_compact_scenario_identity(self) -> None:
        result = project_response({
            "data": [{
                "id": "unit-1", "name": "Project", "description": "Tender",
                "roles": ["owner"], "photo": "PRIVATE-PHOTO",
                "cashflows": [{
                    "id": "cf-1", "unit_id": "unit-1", "name": "Base",
                    "description": "Scenario", "contract_value": 100,
                    "activities": [{"id": "a-1"}], "inflow": [100],
                }],
            }],
            "pages": 2, "token": "SECRET",
        }, ProjectListResponse)

        self.assertEqual(result, {
            "data": [{
                "id": "unit-1", "name": "Project", "description": "Tender",
                "cashflows": [{
                    "id": "cf-1", "unit_id": "unit-1", "name": "Base",
                    "description": "Scenario",
                }],
            }],
            "pages": 2,
        })

    def test_portable_projection_excludes_server_state_and_preserves_source_nulls(self) -> None:
        result = project_response({
            "format": "cashflowpot.cashflow", "version": 1, "token": "SECRET",
            "cashflow": {
                "id": "cf-1", "unit_id": "unit-1", "name": "Tender",
                "inflow_curve_type": None, "contract_value": 100,
                "summary": {"total_inflow": 100}, "inflow": [100],
                "financing_facilities": [{"id": "f-1", "name": "Debt"}],
                "activities": [{
                    "id": "a-1", "cashflow_id": "cf-1", "name": "Work",
                    "activity_mode": "scheduled_cost", "cost_schedule_json": [0, 100],
                    "created_by": "PRIVATE", "cash_flow_json": {"flow": [100]},
                }],
            },
        }, PortableResponse)

        self.assertEqual(result, {
            "format": "cashflowpot.cashflow", "version": 1,
            "cashflow": {
                "name": "Tender", "inflow_curve_type": None, "contract_value": 100,
                "financing_facilities": [{"id": "f-1", "name": "Debt"}],
                "activities": [{
                    "name": "Work", "activity_mode": "scheduled_cost",
                    "cost_schedule_json": [0, 100],
                }],
            },
        })

    def test_results_properties_retain_source_inputs_without_duplicate_cached_results(self) -> None:
        result = project_response({
            "id": "cf-1", "netflow": [-10, 15],
            "properties": {
                "contract": {"contract_value": 100, "advance": 0.1, "token": "SECRET"},
                "forecast": {"wieb": 0.2, "interest_rate": 0.005, "inflow_curve_type": None},
                "activities": [{"id": "a-1", "start": 0, "cash_flow_json": {}}],
                "financing": [{"id": "f-1", "limit": None}],
                "units": {
                    "period_index_base": 0, "percentages": "fraction",
                    "interest_rate_basis": "per_model_period",
                    "amount_unit": "project_currency", "period_unit": "model_period",
                },
            },
        }, ResultsResponse)

        self.assertEqual(result["netflow"], [-10, 15])
        self.assertEqual(result["properties"]["contract"], {"contract_value": 100, "advance": 0.1})
        self.assertEqual(result["properties"]["activities"], [{"id": "a-1", "start": 0}])
        self.assertIsNone(result["properties"]["forecast"]["inflow_curve_type"])

    def test_arbitrary_messages_cannot_echo_credentials(self) -> None:
        source = {"message": "Bearer PRIVATE-SECRET", "token": "SECRET"}
        self.assertEqual(project_response(source, MessageResponse), {
            "message": "CashflowPot request completed.",
        })
        self.assertEqual(source["message"], "Bearer PRIVATE-SECRET")
        self.assertEqual(project_response({"message": "Activity deleted successfully"}, MessageResponse), {
            "message": "Activity deleted successfully",
        })

    def test_invalid_backend_shapes_raise_only_a_safe_error(self) -> None:
        invalid = (
            "PRIVATE-SECRET", [], None,
            {"data": {"activities": "PRIVATE-SECRET"}},
            {"data": {"contract_value": "PRIVATE-SECRET"}},
            {"data": {"contract_value": float("inf")}},
        )
        for value in invalid:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ToolError) as raised:
                    project_response(value, CashflowResponse)
                self.assertEqual(str(raised.exception), "CashflowPot returned an invalid response")

    def test_period_schedule_rejects_unknown_keys_without_echoing_them(self) -> None:
        with self.assertRaises(ToolError) as raised:
            project_response({"data": {"name": "Debt", "draw_schedule": {"TOKEN-SECRET": 10}}}, FacilityResponse)
        self.assertNotIn("SECRET", str(raised.exception))

    def test_all_public_envelopes_accept_sparse_stub_responses_without_filling_fields(self) -> None:
        for response_type in (
            ProjectResponse, ProjectListResponse, CashflowResponse, ActivityResponse,
            ActivityListResponse, FacilityListResponse, FacilityResponse,
            MessageResponse, ExcelResponse, ActivityTypesResponse,
            FacilityPresetsResponse, PortableResponse, ResultsResponse,
        ):
            with self.subTest(response_type=response_type.__name__):
                self.assertEqual(project_response({"token": "SECRET"}, response_type), {})

    def test_schema_declares_closed_nested_objects_and_concrete_financial_fields(self) -> None:
        schema = TypeAdapter(CashflowResponse).json_schema()
        self.assertFalse(schema["additionalProperties"])
        definitions = schema["$defs"]
        for name in ("CashflowSnapshot", "Activity", "Facility", "Summary", "FacilityRow"):
            with self.subTest(definition=name):
                self.assertFalse(definitions[name]["additionalProperties"])
        self.assertIn("contract_value", definitions["CashflowSnapshot"]["properties"])
        self.assertIn("minimum_pre_financing_period", definitions["Summary"]["properties"])
        self.assertIn("available_limit", definitions["FacilityRow"]["properties"])
        schedule = definitions["Facility"]["properties"]["draw_schedule"]
        self.assertFalse(schedule["additionalProperties"])
        self.assertIn(r"^\s*[+-]?\d(?:_?\d)*\s*$", schedule["patternProperties"])

    def test_exported_schema_accepts_numeric_period_schedules_and_nullable_capacity(self) -> None:
        response = {
            "data": {
                "id": "cf-1", "contract_value": 125000,
                "financing_facilities": [{
                    "id": "f-1", "name": "Debt", "limit": None,
                    "draw_schedule": {"0": 100.5, "12": 200},
                    "repayment_schedule": {"14": 300.5},
                }],
                "facility_rows": [{"id": "f-1", "available_limit": [None, 0, 25.5]}],
            },
        }
        projected = project_response(response, CashflowResponse)
        jsonschema.validate(projected, TypeAdapter(CashflowResponse).json_schema())

    def test_facility_cost_preset_fields_are_preserved(self) -> None:
        preset = {
            "key": "overdraft", "type": "Overdraft",
            "draw_method": "automatic_shortfall", "repayment_method": "cashflow_sweep",
            "revolving": True, "interest_rate": 0.005, "fees": 0.0,
            "interest_rate_basis": "per_period", "fees_basis": "fixed_amount",
            "costs_note": "Editable illustrative simulation costs, not lender terms.",
        }
        response = project_response({"data": [preset], "token": "SECRET"}, FacilityPresetsResponse)
        self.assertEqual(response, {"data": [preset]})
        jsonschema.validate(response, TypeAdapter(FacilityPresetsResponse).json_schema())


if __name__ == "__main__":
    unittest.main()
