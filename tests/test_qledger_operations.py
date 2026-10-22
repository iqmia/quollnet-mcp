import json
import unittest
from dataclasses import replace
from unittest.mock import patch
from email.parser import BytesParser
from email.policy import default
import httpx
from tests.qledger_support import U, R, A, E, client
from tests.test_qledger_journals import journal


class QledgerOperationTests(unittest.IsolatedAsyncioTestCase):
    async def test_atomic_json_multipart_and_exact_retry(self):
        from quollnet_mcp.qledger.tools import operations as t
        from quollnet_mcp.qledger.models import FileInput
        from quollnet_mcp.qledger.models_records import OperationRequest

        seen = []
        fail = False

        def handler(req):
            seen.append(req)
            if fail:
                raise httpx.ReadTimeout("lost", request=req)
            return httpx.Response(
                201,
                json={
                    "records": {"invoice": R},
                    "attachments": {"original": A},
                    "journal_entry": E,
                    "links": [],
                },
            )

        op = OperationRequest.model_validate(
            {
                "records": [
                    {
                        "key": "invoice",
                        "type": "invoice",
                        "data": {"total": "12.123456"},
                    }
                ],
                "attachments": [{"key": "original", "file_field": "invoice_file"}],
                "journal": journal(),
                "links": [
                    {
                        "source": {"kind": "record", "key": "invoice"},
                        "target": {"kind": "journal_entry", "key": "journal"},
                    },
                    {
                        "source": {"kind": "attachment", "key": "original"},
                        "target": {"kind": "record", "key": "invoice"},
                    },
                ],
                "post_journal": True,
                "post_records": [
                    {
                        "kind": "record",
                        "id": R,
                        "version": 7,
                        "reviewed_attachments": {A: "hash"},
                    }
                ],
            }
        )
        files = [FileInput(
                filename="original.pdf",
                download_url="https://files.oaiusercontent.com/original",
                file_id="file_1",
                mime_type="application/pdf",
            )]
        async with client(handler) as c:
            with (
                patch.object(t, "qledger_client", c),
                patch.object(t, "download_file", return_value=("original.pdf", b"pdf", "application/pdf")),
                patch.object(t.auth, "unit_token", return_value="unit"),
            ):
                first = await t.execute_qledger_operation(U, op, "stable-key", files)
                self.assertEqual(first["journal_entry"], E)
                self.assertEqual(len(seen), 1)

                def parts(req):
                    return list(
                        BytesParser(policy=default)
                        .parsebytes(
                            b"Content-Type: "
                            + req.headers["content-type"].encode()
                            + b"\r\n\r\n"
                            + req.content
                        )
                        .iter_parts()
                    )

                body = parts(seen[-1])
                self.assertEqual(
                    [p.get_param("name", header="content-disposition") for p in body],
                    ["payload", "invoice_file"],
                )
                payload = json.loads(body[0].get_payload(decode=True))
                self.assertEqual(payload["post_records"][0]["version"], 7)
                self.assertEqual(
                    payload["post_records"][0]["reviewed_attachments"], {A: "hash"}
                )
                self.assertEqual(body[1].get_payload(decode=True), b"pdf")
                await t.execute_qledger_operation(U, op, "stable-key", files)
                self.assertEqual(
                    parts(seen[-1])[0].get_payload(decode=True),
                    body[0].get_payload(decode=True),
                )
                self.assertEqual(seen[-1].headers["Idempotency-Key"], "stable-key")
                fail = True
                before = len(seen)
                with self.assertRaisesRegex(Exception, "same idempotency key"):
                    await t.execute_qledger_operation(U, op, "stable-key", files)
                self.assertEqual(len(seen), before + 1)
                fail = False
                await t.execute_qledger_operation(
                    U,
                    OperationRequest(
                        records=[{"key": "r", "type": "invoice", "data": None}]
                    ),
                    "json-key",
                )
                self.assertEqual(seen[-1].headers["content-type"], "application/json")
                self.assertIs(json.loads(seen[-1].content)["post_journal"], False)
                before = len(seen)
                for bad in [None, [], files + files]:
                    with self.assertRaises(ValueError):
                        await t.execute_qledger_operation(U, op, "key", bad)
                self.assertEqual(len(seen), before)
                c.settings = replace(c.settings, qledger_max_batch_file_bytes=2)
                with patch.object(t, "download_file", side_effect=ValueError("File exceeds the configured transfer limit")), self.assertRaises(ValueError):
                    await t.execute_qledger_operation(U, op, "key", files)
