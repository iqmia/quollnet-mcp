import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.cashflowpot.models import (
    FinancingFacilityInput,
    FinancingFacilityUpdate,
)


class FinancingFacilitySchemaTests(unittest.TestCase):
    def test_create_and_update_schema_expose_all_qflow_financing_fields(self) -> None:
        expected = {
            "name",
            "type",
            "draw_method",
            "repayment_method",
            "start",
            "end",
            "limit",
            "revolving",
            "interest_rate",
            "fees",
            "sweep_priority",
            "draw_schedule",
            "repayment_schedule",
            "advance_portion",
            "repayment_percent",
            "installment_start",
            "installment_interval",
            "installment_count",
        }
        self.assertTrue(expected.issubset(FinancingFacilityInput.model_fields))
        self.assertTrue(expected.issubset(FinancingFacilityUpdate.model_fields))

    def test_schedules_and_ppc_fields_round_trip_without_recalculation(self) -> None:
        facility = FinancingFacilityInput(
            name="LC",
            type="LC",
            draw_method="scheduled",
            repayment_method="percent_of_ppc",
            start=0,
            draw_schedule={"0": 100000, "4": 50000},
            repayment_percent=0.25,
            advance_portion=0.8,
        )
        payload = facility.model_dump(exclude_none=True)
        self.assertEqual(payload["draw_schedule"], {"0": 100000.0, "4": 50000.0})
        self.assertEqual(payload["repayment_percent"], 0.25)
        self.assertEqual(payload["advance_portion"], 0.8)


if __name__ == "__main__":
    unittest.main()
