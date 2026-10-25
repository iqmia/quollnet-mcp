import json
import unittest
from unittest.mock import patch

import httpx

from tests.qledger_support import A, E, R, U, client


class PostableLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_classification_and_atomic_issuance_reach_backend(self):
        from quollnet_mcp.qledger.models_accounting import PostRequest
        from quollnet_mcp.qledger.models_documents import DocumentIssueRequest
        from quollnet_mcp.qledger.models_records import (
            OperationRequest,
            RecordCreate,
            RecordPost,
            RecordQuery,
        )
        from quollnet_mcp.qledger.tools import documents, journals, records

        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"id": R, "status": "posted"})

        issue = {
            "version": 3,
            "reviewed_records": {},
            "reviewed_attachments": {},
            "issuer_name": "Quoll",
        }
        async with client(handler) as connection:
            with (
                patch.object(records, "qledger_client", connection),
                patch.object(journals, "qledger_client", connection),
                patch.object(documents, "qledger_client", connection),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.unit_token",
                    return_value="unit",
                ),
            ):
                await records.create_qledger_record(
                    U, RecordCreate(type="party", data={}, is_postable=False), "create"
                )
                assert json.loads(seen[-1].content)["is_postable"] is False
                await records.list_qledger_records(U, RecordQuery(is_postable=False))
                assert seen[-1].url.params["is_postable"] == "false"
                await records.post_qledger_record(
                    U,
                    R,
                    RecordPost(
                        version=2, reviewed_attachments={}, document_issues={R: issue}
                    ),
                )
                assert json.loads(seen[-1].content)["document_issues"][R] == {
                    **issue,
                    "asset_attachment_ids": {},
                    "filename": "document.pdf",
                }
                # Inbound supplier documents have no QTypeset rendering. Their
                # posting call forwards evidence without an issuance request.
                shared_pdf = "424c1e0343fd27d150b83643764a140d183848afedf6d1096720835b3afed86a"
                await records.post_qledger_record(
                    U,
                    R,
                    RecordPost(
                        version=1,
                        reviewed_records={E: 1},
                        reviewed_attachments={A: shared_pdf},
                    ),
                )
                self.assertEqual(
                    json.loads(seen[-1].content),
                    {
                        "version": 1,
                        "reviewed_records": {E: 1},
                        "reviewed_attachments": {A: shared_pdf},
                        "document_issues": {},
                    },
                )
                self.assertEqual(
                    seen[-1].url.path,
                    f"/api/units/{U}/records/{R}/post",
                )
                await journals.post_qledger_transaction(
                    U,
                    E,
                    PostRequest(
                        version=2,
                        reviewed_evidence={"records": {R: 3}, "attachments": {}},
                        document_issues={R: issue},
                    ),
                )
                assert (
                    json.loads(seen[-1].content)["document_issues"][R]["issuer_name"]
                    == "Quoll"
                )
                await documents.issue_qledger_record(
                    U,
                    E,
                    DocumentIssueRequest(version=2, document_issues={R: issue}),
                    "issue",
                )
                assert (
                    json.loads(seen[-1].content)["document_issues"][R]["version"] == 3
                )
                operation = OperationRequest(
                    records=[
                        {
                            "key": "party",
                            "type": "party",
                            "data": {},
                            "is_postable": False,
                        }
                    ],
                    document_issues={R: issue},
                )
                assert operation.model_dump()["records"][0]["is_postable"] is False
