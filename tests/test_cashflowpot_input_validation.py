"""Input contracts reject invalid source values without inventing backend defaults."""

import os
import unittest

from pydantic import ValidationError

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.cashflowpot.models import (
    ActivityInput,
    ActivityUpdate,
    CashflowInput,
    CashflowUpdate,
    FinancingFacilityInput,
    FinancingFacilityUpdate,
    PortableCashflowDocument,
    ProjectInput,
    ProjectUpdate,
)


class CashflowPotInputValidationTests(unittest.TestCase):
    def test_activity_and_scenario_names_match_database_capacity(self) -> None:
        for model, source in (
            (ActivityInput, {"cost": 1, "duration": 1}),
            (ActivityUpdate, {}), (CashflowInput, {}), (CashflowUpdate, {}),
        ):
            with self.subTest(model=model.__name__):
                model(name="N" * 64, **source)
                with self.assertRaises(ValidationError):
                    model(name="N" * 65, **source)

    def test_backend_constrained_values_are_enums(self) -> None:
        cases = [
            (ActivityInput, {"name": "Work", "cost": 1, "duration": 1}, "activity_mode"),
            (ActivityInput, {"name": "Work", "cost": 1, "duration": 1}, "distribution_type"),
            (ActivityUpdate, {}, "activity_mode"),
            (ActivityUpdate, {}, "distribution_type"),
            (CashflowInput, {"name": "Scenario"}, "inflow_curve_type"),
            (CashflowUpdate, {}, "inflow_curve_type"),
            (FinancingFacilityInput, {"name": "Facility"}, "draw_method"),
            (FinancingFacilityInput, {"name": "Facility"}, "repayment_method"),
            (FinancingFacilityUpdate, {}, "draw_method"),
            (FinancingFacilityUpdate, {}, "repayment_method"),
        ]
        for model, required, field in cases:
            with self.subTest(model=model.__name__, field=field):
                with self.assertRaises(ValidationError):
                    model.model_validate({**required, field: "unsupported"})
                schema = model.model_json_schema()["properties"][field]
                self.assertTrue(any("enum" in choice for choice in schema["anyOf"]))

    def test_category_facility_type_and_duration_units_remain_free_text(self) -> None:
        activity = ActivityInput(
            name="Work", activity_type="Custom category", cost=100, duration=2,
            duration_units="Fortnights",
        )
        self.assertEqual(activity.activity_type, "Custom category")
        self.assertEqual(activity.duration_units, "Fortnights")
        self.assertEqual(FinancingFacilityInput(name="Loan", type="Custom product").type,
                         "Custom product")

    def test_unbounded_money_and_rates_reject_nonfinite_values_and_booleans(self) -> None:
        cases = [
            (ProjectInput, {"name": "Project"}, "contract_value"),
            (ActivityInput, {"name": "Work", "duration": 1}, "cost"),
            (ActivityUpdate, {}, "cost"),
            (CashflowInput, {"name": "Scenario"}, "contract_value"),
            (CashflowInput, {"name": "Scenario"}, "interest_rate"),
            (CashflowUpdate, {}, "contract_value"),
            (CashflowUpdate, {}, "interest_rate"),
            (FinancingFacilityInput, {"name": "Facility"}, "limit"),
            (FinancingFacilityInput, {"name": "Facility"}, "interest_rate"),
            (FinancingFacilityInput, {"name": "Facility"}, "fees"),
            (FinancingFacilityUpdate, {}, "limit"),
            (FinancingFacilityUpdate, {}, "interest_rate"),
            (FinancingFacilityUpdate, {}, "fees"),
        ]
        for model, required, field in cases:
            for value in (float("inf"), float("-inf"), float("nan"), True):
                with self.subTest(model=model.__name__, field=field, value=value):
                    with self.assertRaises(ValidationError):
                        model.model_validate({**required, field: value})

    def test_activity_schedules_reject_negative_nonfinite_and_boolean_amounts(self) -> None:
        for model, required in ((ActivityInput, {"name": "Manual", "distribution_type": "manual"}),
                                (ActivityUpdate, {})):
            for value in (-1, float("inf"), float("nan"), True):
                with self.subTest(model=model.__name__, value=value):
                    with self.assertRaises(ValidationError):
                        model.model_validate({**required, "cost_schedule_json": [100, value]})

    def test_flags_and_periods_do_not_coerce_non_backend_source_types(self) -> None:
        for model, required, field in (
            (FinancingFacilityInput, {"name": "Facility"}, "revolving"),
            (FinancingFacilityUpdate, {}, "revolving"),
            (CashflowInput, {"name": "Scenario"}, "use_independent_inflow_curve"),
            (CashflowUpdate, {}, "use_independent_inflow_curve"),
        ):
            for value in (1, "false"):
                with self.subTest(model=model.__name__, field=field, value=value):
                    with self.assertRaises(ValidationError):
                        model.model_validate({**required, field: value})
        for value in (True, 1.5):
            with self.subTest(start=value):
                with self.assertRaises(ValidationError):
                    ActivityUpdate(start=value)

    def test_facility_schedules_validate_period_keys_and_amounts(self) -> None:
        for model, required in ((FinancingFacilityInput, {"name": "Facility"}),
                                (FinancingFacilityUpdate, {})):
            for field in ("draw_schedule", "repayment_schedule"):
                for schedule in ({"0": -1}, {"0": float("inf")}, {"0": float("nan")},
                                 {"0": True}, {"-1": 1}, {"1.5": 1}, {"later": 1}):
                    with self.subTest(model=model.__name__, field=field, schedule=schedule):
                        with self.assertRaises(ValidationError):
                            model.model_validate({**required, field: schedule})
                self.assertEqual(model.model_validate({**required, field: {"0": 0}})
                                 .model_dump(exclude_unset=True)[field], {"0": 0.0})

    def test_unknown_facility_fields_are_rejected_including_nested_create(self) -> None:
        for model, required in ((FinancingFacilityInput, {"name": "Facility"}),
                                (FinancingFacilityUpdate, {})):
            with self.subTest(model=model.__name__):
                with self.assertRaises(ValidationError):
                    model.model_validate({**required, "interest_arte": 0.1})
        with self.assertRaises(ValidationError):
            CashflowInput(name="Scenario", financing_facilities=[{"name": "OD", "fees": -1}])
        with self.assertRaises(ValidationError):
            CashflowInput(name="Scenario", financing_facilities=[{"name": "OD", "typo": 1}])
        self.assertIsInstance(CashflowInput(name="Scenario", financing_facilities=[{"name": "OD"}])
                              .financing_facilities[0], FinancingFacilityInput)

    def test_facility_creation_omits_backend_defaulted_fields_and_preserves_zero(self) -> None:
        facility = FinancingFacilityInput(name="OD", type="Overdraft")
        self.assertEqual(facility.model_dump(exclude_none=True), {"name": "OD", "type": "Overdraft"})
        explicit = FinancingFacilityInput(name="OD", interest_rate=0, fees=0, revolving=False)
        self.assertEqual(explicit.model_dump(exclude_none=True),
                         {"name": "OD", "interest_rate": 0.0, "fees": 0.0, "revolving": False})

    def test_partial_updates_preserve_explicit_nulls_and_zeros(self) -> None:
        update = FinancingFacilityUpdate(interest_rate=None, fees=0, limit=None)
        self.assertEqual(update.model_dump(exclude_unset=True),
                         {"interest_rate": None, "fees": 0.0, "limit": None})
        self.assertEqual(FinancingFacilityUpdate().model_dump(exclude_unset=True), {})
        self.assertEqual(ActivityUpdate(start=0).model_dump(exclude_unset=True), {"start": 0})

    def test_portable_format_and_version_are_literal_and_cashflow_is_typed(self) -> None:
        for wrong in ({"format": "other"}, {"version": 2}):
            with self.subTest(wrong=wrong):
                with self.assertRaises(ValidationError):
                    PortableCashflowDocument(cashflow={"name": "Scenario"}, **wrong)
        for cashflow in ({"name": "Scenario", "workflow": []},
                         {"name": "Scenario", "activities": [{"name": "Work", "cost": -1, "duration": 1}]},
                         {"name": "Scenario", "financing_facilities": [{"name": "OD", "fees": -1}]}):
            with self.subTest(cashflow=cashflow):
                with self.assertRaises(ValidationError):
                    PortableCashflowDocument(cashflow=cashflow)
        self.assertIsInstance(PortableCashflowDocument(cashflow={"name": "Scenario"}).cashflow,
                              CashflowInput)

    def test_portable_current_and_legacy_source_fields_round_trip(self) -> None:
        source = {
            "format": "cashflowpot.cashflow", "version": 1,
            "cashflow": {
                "name": "Exported", "inflow_curve_type": None, "inflow_curve_skew": None,
                "financing_facilities": [{"id": "existing-od", "name": "OD", "type": "Overdraft",
                    "draw_method": "automatic_shortfall", "repayment_method": "cashflow_sweep",
                    "limit": None, "fees": 0, "interest_rate": 0.01}],
                "activities": [
                    {"name": "Legacy", "activity_type": "linear", "activity_mode": None,
                     "distribution_type": None, "duration_units": "Periods", "cost": 100,
                     "duration": 1, "start": 0, "cost_schedule_json": None},
                    {"name": "Scheduled", "activity_mode": "scheduled_cost",
                     "distribution_type": "manual", "cost_schedule_json": [0, 10]},
                ],
            },
        }
        document = PortableCashflowDocument.model_validate(source)
        self.assertEqual(document.model_dump(exclude_unset=True), source)

    def test_all_input_properties_have_meaningful_descriptions(self) -> None:
        for model in (ProjectInput, ProjectUpdate, ActivityInput, ActivityUpdate, CashflowInput,
                      CashflowUpdate, FinancingFacilityInput, FinancingFacilityUpdate,
                      PortableCashflowDocument):
            for name, field in model.model_fields.items():
                with self.subTest(model=model.__name__, field=name):
                    self.assertTrue(field.description and len(field.description) > 15)


if __name__ == "__main__":
    unittest.main()
