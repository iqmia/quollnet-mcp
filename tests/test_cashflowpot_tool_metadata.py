import os
import unittest

from jsonschema import Draft202012Validator

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from combined_app import cashflowpot_mcp
from tests.test_cashflowpot_full_tools import EXPECTED_TOOLS


class PublicToolMetadataTests(unittest.TestCase):
    def test_all_tool_contracts_and_annotations_match_effects(self):
        reads = {
            "list_cashflow_projects", "get_cashflow_project", "get_cashflow",
            "get_cashflow_results", "export_cashflow_json", "get_activity",
            "get_activity_types", "list_deleted_activities",
            "list_financing_facility_presets", "export_cashflow_excel",
        }
        overwrites = {
            "update_cashflow_project", "update_cashflow", "update_activity",
            "update_financing_facility", "set_financing_facility_order",
        }
        tools = cashflowpot_mcp._tool_manager._tools
        self.assertEqual(set(tools), EXPECTED_TOOLS)
        for name, tool in tools.items():
            with self.subTest(tool=name):
                hints = tool.annotations
                self.assertIs(hints.read_only_hint, name in reads)
                self.assertIs(hints.destructive_hint, name.startswith(("delete_", "hard_delete_")) or name in overwrites)
                self.assertIs(hints.open_world_hint, False)
                self.assertGreater(len(tool.description), 60)
                self.assertIsNotNone(tool.output_schema)
                self.assertIn("properties", tool.output_schema)
                self.assertNotEqual(tool.output_schema.get("additionalProperties"), True)
                Draft202012Validator.check_schema(tool.parameters)
                Draft202012Validator.check_schema(tool.output_schema)
                for field in ("unit_id", "cashflow_id", "activity_id", "facility_id"):
                    if field in tool.parameters.get("properties", {}):
                        self.assertTrue(tool.parameters["properties"][field].get("description"))

    def test_irreversible_tools_advertise_confirmation_and_cascade(self):
        for name in ("hard_delete_cashflow_project", "hard_delete_cashflow", "hard_delete_activity"):
            tool = cashflowpot_mcp._tool_manager._tools[name]
            self.assertIn("confirm_permanent", tool.parameters["properties"])
            self.assertIn("permanent", tool.description.lower())
            self.assertIn("cannot be undone", tool.description.lower())


if __name__ == "__main__":
    unittest.main()
