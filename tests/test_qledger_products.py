import unittest
from unittest.mock import patch

import httpx

from tests.qledger_support import U, client, settings


class ProductToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_keeps_structured_interception_and_scope(self):
        from quollnet_mcp.qledger.tools import records
        from quollnet_mcp.qledger.models_records import ProductSearchQuery

        seen = []
        payload = {
            "status": "not_found",
            "query": "cement",
            "items": [],
            "total": 0,
            "actions": [{"type": "ad_hoc"}, {"type": "new_record"}],
        }

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=payload)

        async with client(handler) as connection:
            with (
                patch.object(records, "qledger_client", connection),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.unit_token",
                    return_value="unit",
                ),
            ):
                result = await records.search_qledger_products(
                    U, ProductSearchQuery(q="cement", page=2)
                )
        self.assertEqual(result, payload)
        self.assertEqual(seen[0].url.path, "/api/units/" + U + "/products/search")
        self.assertEqual(seen[0].url.params["q"], "cement")
        self.assertEqual(seen[0].url.params["page"], "2")
        self.assertNotIn("Idempotency-Key", seen[0].headers)

    async def test_search_registration_is_read_only_and_explains_confirmation(self):
        from quollnet_mcp.qledger.server import build_qledger_server
        from quollnet_mcp.qledger.instructions import QLEDGER_INSTRUCTIONS

        tools = await build_qledger_server(settings()).list_tools()
        tool = next(t for t in tools if t.name == "search_qledger_products")
        self.assertTrue(tool.annotations.read_only_hint)
        self.assertFalse(tool.annotations.destructive_hint)
        self.assertIn("confirmation", tool.description)
        self.assertIn("line_id", QLEDGER_INSTRUCTIONS)
        self.assertIn("ad_hoc", QLEDGER_INSTRUCTIONS)
