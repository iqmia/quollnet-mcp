"""Advisory checks and reference schemas must be discoverable through MCP."""

import unittest
from copy import deepcopy
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from tests.qledger_support import U, settings


class CanonicalLinesTests(unittest.TestCase):
    def test_checked_in_schema_and_example_match_tool_contract(self):
        import json
        from pathlib import Path

        from quollnet_mcp.qledger.line_guidance import line_item_guidance

        guide = line_item_guidance()
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(
            json.loads(
                (root / "docs/schemas/qentries-document-lines.schema.json").read_text()
            ),
            guide.document_data_schema,
        )
        self.assertEqual(
            json.loads(
                (root / "docs/examples/qentries-invoice-record.json").read_text()
            ),
            guide.canonical_example,
        )

    def test_reference_schema_and_example_are_consistent(self):
        from quollnet_mcp.qledger.line_guidance import line_item_guidance
        from quollnet_mcp.qledger.models_lines import DocumentData
        from quollnet_mcp.qledger.models_records import RecordCreate

        guide = line_item_guidance()
        example = deepcopy(guide.canonical_example)
        self.assertEqual(example["type"], "invoice")
        self.assertEqual(example["data"]["lines"][0]["line_type"], "catalog")
        self.assertEqual(example["data"]["lines"][1]["line_type"], "ad_hoc")
        DocumentData.model_validate(example["data"])
        RecordCreate.model_validate(example)
        self.assertEqual(
            sum(Decimal(row["total"]) for row in example["data"]["lines"]),
            Decimal(example["data"]["total"]),
        )
        schema = guide.document_data_schema
        self.assertEqual(
            schema["properties"]["lines"]["items"]["discriminator"]["propertyName"],
            "line_type",
        )
        self.assertIn("CatalogLine", schema["$defs"])
        self.assertIn("AdHocLine", schema["$defs"])
        self.assertTrue(schema["additionalProperties"])

    def test_ad_hoc_required_fields_and_extra_metadata(self):
        from quollnet_mcp.qledger.models_lines import DocumentLine

        adapter = TypeAdapter(DocumentLine)
        line = {
            "line_id": "1",
            "line_type": "ad_hoc",
            "description": "Installation",
            "quantity": "-2",
            "unit_price": "10.00",
            "total": "-20.00",
            "budget_code": "WP",
            "source_line": {"id": "old-1"},
        }
        parsed = adapter.validate_python(line)
        self.assertEqual(parsed.model_dump(exclude_unset=True), line)
        for field in ("description", "quantity", "unit_price", "total"):
            with self.subTest(field=field):
                missing = {key: value for key, value in line.items() if key != field}
                with self.assertRaises(ValidationError):
                    adapter.validate_python(missing)
        with self.assertRaises(ValidationError):
            adapter.validate_python({**line, "product_id": U})

    def test_catalog_can_resolve_snapshot_and_price_from_product(self):
        from quollnet_mcp.qledger.models_lines import DocumentLine

        line = TypeAdapter(DocumentLine).validate_python(
            {"line_id": "1", "line_type": "catalog", "sku": "WP-001", "quantity": "2"}
        )
        self.assertIsNone(line.unit_price)
        self.assertIsNone(line.product_id)
        self.assertIsNone(line.description)

    def test_canonical_money_is_exact_signed_bounded_decimal_text(self):
        from quollnet_mcp.qledger.models_lines import DocumentLine

        adapter = TypeAdapter(DocumentLine)
        base = {
            "line_id": "1",
            "line_type": "ad_hoc",
            "description": "Test",
            "quantity": "1",
            "unit_price": "9007199254740993.01",
            "total": "9007199254740993.01",
        }
        self.assertEqual(
            adapter.validate_python(base).unit_price, "9007199254740993.01"
        )
        for invalid in (
            True,
            1.25,
            "NaN",
            "Infinity",
            "1000000000000000000",
            "0.1234567890123",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                adapter.validate_python({**base, "unit_price": invalid})

    def test_omitted_numeric_fields_are_not_advertised_as_nullable(self):
        from quollnet_mcp.qledger.models_lines import DocumentData, DocumentLine

        line = {
            "line_id": "1",
            "line_type": "ad_hoc",
            "description": "Test",
            "quantity": "1",
            "unit_price": "10",
            "total": "10",
        }
        adapter = TypeAdapter(DocumentLine)
        for field in (
            "discount_percent",
            "discount_amount",
            "tax_rate",
            "subtotal",
            "taxable_amount",
            "tax_amount",
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                adapter.validate_python({**line, field: None})
        schema = DocumentData.model_json_schema()
        tax = schema["$defs"]["AdHocLine"]["properties"]["tax_rate"]
        self.assertNotIn("anyOf", tax)
        self.assertNotIn("default", tax)
        with self.assertRaises(ValidationError):
            DocumentData.model_validate({"lines": [line], "total": None})

    def test_generic_record_data_and_partial_drafts_remain_compatible(self):
        from quollnet_mcp.qledger.models_records import RecordCreate, RecordPatch

        for data in (
            None,
            [],
            "custom",
            {"custom": True},
            {"lines": []},
            {"lines": [{"unresolved": True}]},
        ):
            with self.subTest(data=data):
                self.assertEqual(RecordCreate(type="custom", data=data).data, data)
                self.assertEqual(RecordPatch(version=1, data=data).data, data)


class GuidanceToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_are_read_only_scoped_and_have_typed_output(self):
        from quollnet_mcp.qledger.server import build_qledger_server

        tools = {
            tool.name: tool
            for tool in await build_qledger_server(settings()).list_tools()
        }
        for name in ("check_qledger_tax_identifier", "get_qledger_line_item_guidance"):
            self.assertTrue(tools[name].annotations.read_only_hint)
            self.assertFalse(tools[name].annotations.destructive_hint)
            self.assertIsNotNone(tools[name].output_schema)
        self.assertIn(
            "country_code",
            tools["check_qledger_tax_identifier"].input_schema["required"],
        )

    async def test_check_is_forwarded_to_qentries_without_local_validation(self):
        import json

        import httpx

        from quollnet_mcp.qledger.tools import guidance
        from tests.qledger_support import client

        seen = []
        response = {
            "country_code": "ES",
            "identifier": "ES-foreign-ID",
            "identifier_type": "tax_id",
            "normalized_identifier": "ES-foreign-ID",
            "supported": False,
            "status": "unsupported_country",
            "acceptance_status": "accepted_unchecked",
            "blocking": False,
            "required": True,
            "warnings": ["No validator available"],
            "policy": {"required": True},
        }

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=response)

        async with client(handler) as connection:
            with (
                patch.object(guidance, "qledger_client", connection),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.unit_token",
                    new_callable=AsyncMock,
                    return_value="unit",
                ),
            ):
                result = await guidance.check_qledger_tax_identifier(
                    UUID(U), "ES-foreign-ID", "ES"
                )
        self.assertEqual(result.status, "unsupported_country")
        self.assertEqual(result.acceptance_status, "accepted_unchecked")
        self.assertEqual(seen[0].method, "POST")
        self.assertEqual(seen[0].url.path, "/api/units/" + U + "/tax-identifiers/check")
        self.assertEqual(
            json.loads(seen[0].content),
            {
                "country_code": "ES",
                "identifier": "ES-foreign-ID",
                "identifier_type": "tax_id",
            },
        )

    async def test_backend_errors_are_not_replaced_with_guessed_results(self):
        import httpx
        from mcp.server.mcpserver.exceptions import ToolError

        from quollnet_mcp.qledger.tools import guidance
        from tests.qledger_support import client

        async with client(
            lambda request: httpx.Response(
                403, json={"message": "Permission required: record:view"}
            )
        ) as connection:
            with (
                patch.object(guidance, "qledger_client", connection),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.unit_token",
                    new_callable=AsyncMock,
                    return_value="unit",
                ),
                self.assertRaises(ToolError),
            ):
                await guidance.check_qledger_tax_identifier(UUID(U), "517115897", "PT")

    async def test_unit_authorization_failure_is_preserved(self):
        from mcp.server.mcpserver.exceptions import ToolError

        from quollnet_mcp.qledger.tools import guidance

        with patch.object(
            guidance.auth,
            "unit_token",
            new_callable=AsyncMock,
            side_effect=ToolError("Unit not authorized"),
        ):
            with self.assertRaises(ToolError):
                await guidance.check_qledger_tax_identifier(UUID(U), "517115897", "PT")
            with self.assertRaises(ToolError):
                await guidance.get_qledger_line_item_guidance(UUID(U))

    async def test_sdk_invocation_returns_server_policy_and_line_schema(self):
        from quollnet_mcp.qledger.server import build_qledger_server
        from quollnet_mcp.qledger.tax_identifiers import TaxIdentifierCheck
        from quollnet_mcp.qledger.tools import guidance

        result = TaxIdentifierCheck(
            country_code="PT",
            identifier="517115897",
            identifier_type="tax_id",
            normalized_identifier="517115897",
            supported=True,
            status="checksum_failed",
            checksum_valid=False,
            acceptance_status="accepted_with_warning",
            blocking=False,
            required=False,
            warnings=["Advisory"],
            policy={},
        )
        server = build_qledger_server(settings())
        with (
            patch.object(
                guidance,
                "call",
                new_callable=AsyncMock,
                return_value=result.model_dump(),
            ),
            patch.object(
                guidance.auth, "unit_token", new_callable=AsyncMock, return_value="unit"
            ),
        ):
            checked = await server.call_tool(
                "check_qledger_tax_identifier",
                {"unit_id": U, "identifier": "517115897", "country_code": "PT"},
            )
            guide = await server.call_tool(
                "get_qledger_line_item_guidance", {"unit_id": U}
            )
        self.assertFalse(checked.is_error)
        self.assertEqual(
            checked.structured_content["acceptance_status"], "accepted_with_warning"
        )
        self.assertFalse(guide.is_error)
        self.assertEqual(
            guide.structured_content["document_data_schema"]["title"], "DocumentData"
        )

    def test_override_is_explicit_and_typed_for_writes(self):
        from quollnet_mcp.qledger.models_records import RecordCreate, RecordPatch

        for model, values in (
            (RecordCreate, {"type": "party", "data": {}}),
            (RecordPatch, {"version": 1}),
        ):
            result = model(
                **values, tax_override={"reason": "Approved fictional test identifier"}
            )
            self.assertEqual(
                result.tax_override.reason, "Approved fictional test identifier"
            )
            with self.assertRaises(ValidationError):
                model(**values, tax_override={"reason": " "})
