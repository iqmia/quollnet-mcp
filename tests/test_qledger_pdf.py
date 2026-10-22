import base64
import json
import unittest
from unittest.mock import patch

import httpx

from tests.qledger_support import A, R, U, client, settings

PDF = b"%PDF-1.4\nQTypeset\n%%EOF"


class QledgerPdfTests(unittest.IsolatedAsyncioTestCase):
    async def test_guidance_and_record_rendering_use_qentries_api(self):
        from quollnet_mcp.qledger.tools import documents as t
        from quollnet_mcp.qledger.models_documents import PdfRenderRequest

        seen = []

        def handler(request):
            seen.append(request)
            if request.url.path.endswith("document-design-guidance"):
                return httpx.Response(
                    200,
                    json={
                        "renderer": "qtypeset",
                        "guidance": "Design defaults",
                        "schema": {"properties": {}},
                    },
                )
            return httpx.Response(
                200,
                content=PDF,
                headers={
                    "Content-Type": "application/pdf",
                    "X-QEntries-Record-Version": "3",
                    "X-QEntries-Attachment-Id": A,
                },
            )

        async with client(handler) as c:
            with (
                patch.object(t, "qledger_client", c),
                patch.object(t.auth, "unit_token", return_value="user-unit-token"),
            ):
                guide = await t.get_qledger_document_design_guidance(
                    U, include_schema=True
                )
                self.assertEqual(guide["renderer"], "qtypeset")
                self.assertEqual(seen[-1].url.params["include_schema"], "true")
                result = await t.render_qledger_record_pdf(
                    U,
                    R,
                    PdfRenderRequest(
                        version=3, save_to_record=True, filename="invoice.pdf"
                    ),
                    idempotency_key="stable-pdf-key",
                )
                metadata = json.loads(result.content[0].text)
                self.assertEqual(metadata["attachment_id"], A)
                self.assertEqual(metadata["record_version"], 3)
                self.assertEqual(base64.b64decode(result.content[1].resource.blob), PDF)
                self.assertEqual(
                    result.content[1].resource.uri,
                    f"qledger://units/{U}/attachments/{A}",
                )
                self.assertEqual(seen[-1].url.path, f"/api/units/{U}/records/{R}/pdf")
                self.assertEqual(seen[-1].method, "POST")
                self.assertEqual(
                    seen[-1].headers["Authorization"], "Bearer user-unit-token"
                )
                self.assertEqual(seen[-1].headers["Idempotency-Key"], "stable-pdf-key")
                self.assertNotIn("X-API-Key", seen[-1].headers)
                self.assertEqual(json.loads(seen[-1].content)["version"], 3)

    async def test_preview_does_not_require_key_and_invalid_response_is_rejected(self):
        from quollnet_mcp.qledger.tools import documents as t
        from quollnet_mcp.qledger.models_documents import PdfRenderRequest

        response = httpx.Response(
            200,
            content=PDF,
            headers={
                "Content-Type": "application/pdf",
                "X-QEntries-Record-Version": "1",
            },
        )
        async with client(lambda req: response) as c:
            with (
                patch.object(t, "qledger_client", c),
                patch.object(t.auth, "unit_token", return_value="unit"),
            ):
                result = await t.render_qledger_record_pdf(
                    U, R, PdfRenderRequest(version=1)
                )
                self.assertFalse(json.loads(result.content[0].text)["saved_to_record"])
                with self.assertRaises(ValueError):
                    await t.render_qledger_record_pdf(
                        U, R, PdfRenderRequest(version=1, save_to_record=True)
                    )
                response = httpx.Response(
                    200,
                    content=b"<html>login</html>",
                    headers={"Content-Type": "text/html"},
                )
                with self.assertRaisesRegex(Exception, "PDF"):
                    await t.render_qledger_record_pdf(U, R, PdfRenderRequest(version=1))

    async def test_design_and_render_tools_are_registered(self):
        from quollnet_mcp.qledger.server import build_qledger_server

        tools = {t.name: t for t in await build_qledger_server(settings()).list_tools()}
        self.assertTrue(
            tools["get_qledger_document_design_guidance"].annotations.read_only_hint
        )
        self.assertFalse(tools["render_qledger_record_pdf"].annotations.read_only_hint)
        self.assertIn("QTypeset", tools["render_qledger_record_pdf"].description)
