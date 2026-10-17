import os
import unittest

from pydantic import ValidationError

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.cashflowpot.models import ActivityInput, ActivityUpdate


class CashflowPotActivityScheduleContractTests(unittest.TestCase):
    def test_manual_activity_schedule_is_a_dense_zero_based_list(self) -> None:
        activity = ActivityInput(
            name="Manual Work",
            activity_mode="work",
            distribution_type="manual",
            cost_schedule_json=[100, 0, 250],
            start=0,
        )
        self.assertEqual(activity.cost_schedule_json, [100.0, 0.0, 250.0])

    def test_mapping_schedule_is_rejected_before_qflow_call(self) -> None:
        with self.assertRaises(ValidationError):
            ActivityInput(
                name="Manual Work",
                activity_mode="work",
                distribution_type="manual",
                cost_schedule_json={"0": 100, "2": 250},
                start=0,
            )

        with self.assertRaises(ValidationError):
            ActivityUpdate(cost_schedule_json={"0": 100})


if __name__ == "__main__":
    unittest.main()
