"""Advisory checks and reference schemas must be discoverable through MCP."""

import unittest
from copy import deepcopy
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from tests.qledger_support import U, settings


class TaxChecksumTests(unittest.TestCase):
    def test_failed_nipc_preserves_input_and_reports_advisory_result(self):
        from quollnet_mcp.qledger.tax_identifiers import check_tax_identifier

        result = check_tax_identifier("517115897", "PT")
        self.assertEqual(result.identifier, "517115897")
        self.assertEqual(result.status, "failed_checksum")
        self.assertEqual(result.weighted_sum, 175)
        self.assertEqual(result.expected_check_digit, "1")
        self.assertEqual(result.supplied_check_digit, "7")
        self.assertFalse(result.checksum_valid)
        self.assertFalse(result.blocking)
        self.assertEqual(result.verification_status, "unverified")

    def test_checksum_pass_is_not_external_verification(self):
        from quollnet_mcp.qledger.tax_identifiers import check_tax_identifier

        for identifier in ("517115891", "501234560"):
            with self.subTest(identifier=identifier):
                result = check_tax_identifier(identifier, "PT")
                self.assertEqual(result.status, "passed")
                self.assertTrue(result.checksum_valid)
                self.assertEqual(result.verification_status, "unverified")
                self.assertTrue(result.warnings)

    def test_zero_check_digit_for_modulo_zero_and_one(self):
        from quollnet_mcp.qledger.tax_identifiers import check_tax_identifier

        for identifier, remainder in (("500000050", 0), ("501234560", 1)):
            with self.subTest(identifier=identifier):
                result = check_tax_identifier(identifier, "PT")
                self.assertEqual(result.weighted_sum % 11, remainder)
                self.assertEqual(result.expected_check_digit, "0")
                self.assertTrue(result.checksum_valid)

    def test_normalization_is_explicit_and_original_value_is_retained(self):
        from quollnet_mcp.qledger.tax_identifiers import check_tax_identifier

        original = " pt 517-115-897 "
        result = check_tax_identifier(original, "pt")
        self.assertEqual(result.identifier, original)
        self.assertEqual(result.normalized_identifier, "517115897")
        self.assertFalse(result.checksum_valid)

    def test_malformed_values_never_get_repaired_into_valid_numbers(self):
        from quollnet_mcp.qledger.tax_identifiers import check_tax_identifier

        for identifier in (
            "",
            "51711589",
            "5171158910",
            "abc517115891",
            "５１７１１５８９１",
            "017115891",
        ):
            with self.subTest(identifier=identifier):
                result = check_tax_identifier(identifier, "PT")
                self.assertEqual(result.status, "invalid_format")
                self.assertFalse(result.format_valid)
                self.assertIsNone(result.checksum_valid)
                self.assertIsNone(result.expected_check_digit)
                self.assertFalse(result.blocking)

    def test_forbidden_whitespace_is_not_normalized_away(self):
        from quollnet_mcp.qledger.tax_identifiers import check_tax_identifier

        for identifier in (
            "\t517115891\n",
            "\u00a0517115891\u00a0",
            "PT\t517115891",
            "PT\u2003517115891",
        ):
            with self.subTest(identifier=identifier):
                result = check_tax_identifier(identifier, "PT")
                self.assertEqual(result.identifier, identifier)
                self.assertEqual(result.status, "invalid_format")
                self.assertIsNone(result.checksum_valid)
        valid = check_tax_identifier(" PT 517-115-891 ", "PT")
        self.assertEqual(valid.status, "passed")

    def test_unsupported_country_does_not_apply_portuguese_algorithm(self):
        from quollnet_mcp.qledger.tax_identifiers import check_tax_identifier

        result = check_tax_identifier("517115891", "US")
        self.assertEqual(result.status, "unsupported_country")
        self.assertFalse(result.supported)
        self.assertIsNone(result.checksum_valid)
        self.assertIsNone(result.algorithm)
        self.assertFalse(result.blocking)


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
        from quollnet_mcp.qledger.tools import guidance

        server = build_qledger_server(settings())
        tools = {tool.name: tool for tool in await server.list_tools()}
        for name in ("check_qledger_tax_identifier", "get_qledger_line_item_guidance"):
            self.assertIn(name, tools)
            self.assertTrue(tools[name].annotations.read_only_hint)
            self.assertFalse(tools[name].annotations.destructive_hint)
            self.assertIn("unit_id", tools[name].input_schema["required"])
            self.assertIsNotNone(tools[name].output_schema)
        with patch.object(
            guidance.auth, "unit_token", new_callable=AsyncMock, return_value="unit"
        ) as authorize:
            checked = await guidance.check_qledger_tax_identifier(
                UUID(U), "517115897", "PT"
            )
            guide = await guidance.get_qledger_line_item_guidance(UUID(U))
        self.assertFalse(checked.blocking)
        self.assertEqual(checked.status, "failed_checksum")
        self.assertIn("lines", guide.canonical_example["data"])
        self.assertEqual(authorize.await_count, 2)
        authorize.assert_awaited_with(UUID(U))

    async def test_failed_checksum_does_not_block_authorized_record_write(self):
        import json

        import httpx

        from quollnet_mcp.qledger.models_records import RecordPatch
        from quollnet_mcp.qledger.tax_identifiers import check_tax_identifier
        from quollnet_mcp.qledger.tools import records
        from tests.qledger_support import R, client

        checked = check_tax_identifier("517115897", "PT")
        self.assertFalse(checked.checksum_valid)
        payload = {
            "name": "Test N2 LDA",
            "address": {"city": "Lisbon"},
            "tax": {
                "nipc": checked.identifier,
                "verification_status": "unverified",
                "tax_validation_status": "failed_checksum_user_overridden",
            },
        }
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"id": R, "version": 2, "data": payload})

        async with client(handler) as connection:
            with (
                patch.object(records, "qledger_client", connection),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.unit_token",
                    new_callable=AsyncMock,
                    return_value="unit",
                ),
            ):
                result = await records.update_qledger_record(
                    U, R, RecordPatch(version=1, data=payload)
                )
        self.assertEqual(result["version"], 2)
        self.assertEqual(seen[0].method, "PATCH")
        self.assertEqual(json.loads(seen[0].content), {"version": 1, "data": payload})

    async def test_unit_authorization_failure_is_preserved(self):
        from mcp.server.mcpserver.exceptions import ToolError

        from quollnet_mcp.qledger.tools import guidance

        with patch.object(
            guidance.auth,
            "unit_token",
            new_callable=AsyncMock,
            side_effect=ToolError("Unit not authorized"),
        ):
            with self.assertRaisesRegex(ToolError, "Unit not authorized"):
                await guidance.check_qledger_tax_identifier(UUID(U), "517115897", "PT")
            with self.assertRaisesRegex(ToolError, "Unit not authorized"):
                await guidance.get_qledger_line_item_guidance(UUID(U))

    async def test_sdk_invocation_returns_structured_advisory_and_schema(self):
        from quollnet_mcp.qledger.server import build_qledger_server
        from quollnet_mcp.qledger.tools import guidance

        server = build_qledger_server(settings())
        with patch.object(
            guidance.auth, "unit_token", new_callable=AsyncMock, return_value="unit"
        ):
            result = await server.call_tool(
                "check_qledger_tax_identifier",
                {"unit_id": U, "identifier": "517115897", "country_code": "PT"},
            )
            guide = await server.call_tool(
                "get_qledger_line_item_guidance", {"unit_id": U}
            )
        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["status"], "failed_checksum")
        self.assertFalse(result.structured_content["checksum_valid"])
        self.assertFalse(guide.is_error)
        self.assertEqual(
            guide.structured_content["document_data_schema"]["title"], "DocumentData"
        )
