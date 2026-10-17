import unittest
from contextlib import ExitStack
from unittest.mock import patch
import httpx
from tests.qledger_support import U, E, A, L, client


class QledgerAttachmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_attachment_mapping_and_binary_result(self):
        from quollnet_mcp.qledger.tools import attachments as t
        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.models import FileInput, TargetRef, AttachmentQuery

        seen = []

        def handler(req):
            seen.append(req)
            if req.url.path.endswith("/download"):
                return httpx.Response(
                    200,
                    content=b"pdf",
                    headers={"content-type": "application/octet-stream"},
                )
            return httpx.Response(
                200,
                json={
                    "id": A,
                    "original_filename": "invoice.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": 3,
                    "sha256": "c35b21d6ca39aa7cc3b79a705d989f1a6e88b99ab43988d74048799e3db926a3",
                },
            )

        async with client(handler) as c:
            with ExitStack() as s:
                s.enter_context(patch.object(t, "qledger_client", c))
                s.enter_context(patch.object(files, "qledger_client", c))
                s.enter_context(
                    patch(
                        "quollnet_mcp.qledger.tools.common.auth.unit_token",
                        return_value="unit",
                    )
                )
                target = TargetRef(
                    linked_to_object="journal_entry", linked_to_object_id=E
                )
                await t.list_qledger_attachments(
                    U,
                    AttachmentQuery(
                        linked_to_object="journal_entry", linked_to_object_id=E
                    ),
                )
                await t.get_qledger_attachment(U, A)
                await t.upload_qledger_attachment(
                    U,
                    target,
                    FileInput(filename="invoice.pdf", file_base64="cGRm"),
                    "k",
                )
                self.assertIn(b'name="linked_to_object"', seen[-1].content)
                self.assertIn(b'name="file"; filename="invoice.pdf"', seen[-1].content)
                self.assertIn(b"pdf", seen[-1].content)
                self.assertEqual(seen[-1].headers["Idempotency-Key"], "k")
                cases = [
                    (lambda: t.list_qledger_attachment_links(U, A), "GET", "/links"),
                    (
                        lambda: t.link_qledger_attachment(U, A, target, "k"),
                        "POST",
                        "/links",
                    ),
                    (
                        lambda: t.unlink_qledger_attachment(U, A, L),
                        "DELETE",
                        "/links/" + L,
                    ),
                    (
                        lambda: t.replace_qledger_attachment_link(U, A, L, target),
                        "PATCH",
                        "/links/" + L,
                    ),
                ]
                for fn, method, suffix in cases:
                    before = len(seen)
                    await fn()
                    self.assertEqual(len(seen), before + 1)
                    self.assertEqual(
                        (seen[-1].method, seen[-1].url.path),
                        (method, f"/api/units/{U}/attachments/{A}" + suffix),
                    )
                result = await t.download_qledger_attachment(U, A)
                self.assertEqual(result.content[1].resource.blob, "cGRm")
                self.assertEqual(
                    result.content[1].resource.mime_type, "application/pdf"
                )
                self.assertNotIn("cGRm", result.content[0].text)
                self.assertNotIn("unit", result.content[0].text.replace(U, ""))
