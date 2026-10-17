import json
import unittest
from unittest.mock import patch
import httpx
from tests.qledger_support import U, R, E, A, L, client


class QledgerRecordTests(unittest.IsolatedAsyncioTestCase):
    async def test_records_links_and_minimal_responses(self):
        from quollnet_mcp.qledger.tools import records as t
        from quollnet_mcp.qledger.models import VersionRequest, RecordLinkCreate
        from quollnet_mcp.qledger.models_records import (
            RecordCreate,
            RecordPatch,
            RecordPost,
            RecordQuery,
        )

        seen = []
        conflict = False
        minimal = {"id": R, "version": 2, "status": "draft"}

        def handler(req):
            seen.append(req)
            return (
                httpx.Response(409, json={"message": "Record changed"})
                if conflict
                else httpx.Response(200, json=minimal)
            )

        async with client(handler) as c:
            with (
                patch.object(t, "qledger_client", c),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.unit_token",
                    return_value="unit",
                ),
            ):
                target = RecordLinkCreate(
                    linked_to_object="journal_entry",
                    linked_to_object_id=E,
                    version=2,
                    reviewed_attachments={A: "hash"},
                )
                post = RecordPost(version=2, reviewed_attachments={A: "hash"})
                cases = [
                    (
                        lambda: t.list_qledger_records(
                            U,
                            RecordQuery(
                                linked_to_object="journal_entry",
                                linked_to_object_id=E,
                                types="invoice,receipt",
                                page=2,
                            ),
                        ),
                        "GET",
                        "",
                        False,
                    ),
                    (lambda: t.get_qledger_record(U, R), "GET", "/" + R, False),
                    (
                        lambda: t.create_qledger_record(
                            U,
                            RecordCreate(type="invoice", data={"total": "12.12"}),
                            "k",
                        ),
                        "POST",
                        "",
                        True,
                    ),
                    (
                        lambda: t.update_qledger_record(
                            U, R, RecordPatch(version=2, data=None)
                        ),
                        "PATCH",
                        "/" + R,
                        False,
                    ),
                    (
                        lambda: t.delete_qledger_record(
                            U, R, VersionRequest(version=2)
                        ),
                        "DELETE",
                        "/" + R,
                        False,
                    ),
                    (
                        lambda: t.copy_qledger_record(
                            U, R, VersionRequest(version=2), "k"
                        ),
                        "POST",
                        "/" + R + "/copy",
                        True,
                    ),
                    (
                        lambda: t.post_qledger_record(U, R, post),
                        "POST",
                        "/" + R + "/post",
                        False,
                    ),
                    (
                        lambda: t.list_qledger_record_links(U, R),
                        "GET",
                        "/" + R + "/links",
                        False,
                    ),
                    (
                        lambda: t.link_qledger_record(U, R, target, "k"),
                        "POST",
                        "/" + R + "/links",
                        True,
                    ),
                    (
                        lambda: t.unlink_qledger_record(U, R, L),
                        "DELETE",
                        "/" + R + "/links/" + L,
                        False,
                    ),
                    (
                        lambda: t.replace_qledger_record_link(U, R, L, target),
                        "PATCH",
                        "/" + R + "/links/" + L,
                        False,
                    ),
                ]
                for fn, method, suffix, keyed in cases:
                    before = len(seen)
                    self.assertEqual(await fn(), minimal)
                    self.assertEqual(len(seen), before + 1)
                    self.assertEqual(
                        (seen[-1].method, seen[-1].url.path),
                        (method, "/api/units/" + U + "/records" + suffix),
                    )
                    self.assertEqual("Idempotency-Key" in seen[-1].headers, keyed)
                self.assertEqual(seen[0].url.params["types"], "invoice,receipt")
                self.assertEqual(seen[0].url.params["page"], "2")
                self.assertEqual(
                    json.loads(seen[3].content), {"version": 2, "data": None}
                )
                self.assertEqual(json.loads(seen[4].content), {"version": 2})
                conflict = True
                for fn in [
                    lambda: t.post_qledger_record(U, R, post),
                    lambda: t.link_qledger_record(U, R, target, "k"),
                ]:
                    before = len(seen)
                    with self.assertRaisesRegex(Exception, "409.*review"):
                        await fn()
                    self.assertEqual(len(seen), before + 1)
                    payload = json.loads(seen[-1].content)
                    self.assertEqual(payload["version"], 2)
                    self.assertEqual(payload["reviewed_attachments"], {A: "hash"})
