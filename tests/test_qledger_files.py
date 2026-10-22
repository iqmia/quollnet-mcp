import unittest
from unittest.mock import patch
import httpx
from tests.qledger_support import U, A, client


class QledgerFileTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticated_uncached_resource_and_stream_limit(self):
        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.qledger_client import QledgerClientError

        seen = []
        denied = False

        def handler(req):
            seen.append(req)
            return (
                httpx.Response(403, json={"message": "Not allowed"})
                if denied
                else httpx.Response(
                    200, content=b"pdf", headers={"content-type": "application/pdf"}
                )
            )

        async with client(handler) as c:
            with (
                patch.object(files, "qledger_client", c),
                patch.object(
                    files.auth, "unit_token", side_effect=["first", "second", "revoked"]
                ),
            ):
                one = await files.attachment_resource(U, A)
                two = await files.attachment_resource(U, A)
                self.assertEqual(one.blob, "cGRm")
                self.assertEqual(two.blob, "cGRm")
                self.assertEqual(one.mime_type, "application/pdf")
                self.assertEqual(one.uri, f"qledger://units/{U}/attachments/{A}")
                self.assertEqual(
                    [r.headers["Authorization"] for r in seen],
                    ["Bearer first", "Bearer second"],
                )
                denied = True
                with self.assertRaises(Exception):
                    await files.attachment_resource(U, A)
            denied = False
            with self.assertRaises(QledgerClientError):
                await c.download("/api/file", access_token="token", max_bytes=2)
