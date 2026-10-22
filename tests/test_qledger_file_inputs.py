import json
import unittest
from unittest.mock import patch

import httpx

from tests.qledger_support import A, R, U, client, settings

URL = "https://files.oaiusercontent.com/original?secret=redact"


class ChatGPTFileTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_descriptor_uses_complete_chatgpt_file_contract(self):
        from quollnet_mcp.qledger.server import build_qledger_server

        tools = {t.name: t for t in await build_qledger_server(settings()).list_tools()}
        tool = tools["upload_qledger_attachment"]
        self.assertEqual(tool.meta["openai/fileParams"], ["file"])
        schema = tool.input_schema["$defs"]["FileInput"]
        self.assertEqual(set(schema["required"]), {"download_url", "file_id"})
        self.assertTrue(
            {"download_url", "file_id", "mime_type", "file_name", "filename"}
            <= set(schema["properties"])
        )
        self.assertNotIn("file_base64", json.dumps(tool.input_schema))
        self.assertEqual(
            tools["execute_qledger_operation"].meta["openai/fileParams"], ["files"]
        )
        self.assertEqual(
            tools["execute_qledger_operation"].input_schema["properties"]["files"][
                "anyOf"
            ][0]["type"],
            "array",
        )

    async def test_original_download_is_pinned_bounded_and_credential_free(self):
        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.models import FileInput

        requests = []
        raw = b"\x00\xfforiginal\r\n"

        def handler(request):
            requests.append(request)
            return httpx.Response(200, content=raw)

        factory = httpx.MockTransport
        with (
            patch.object(files, "resolve_public_addresses", return_value=["8.8.8.8"]),
            patch.object(
                files.httpx,
                "AsyncHTTPTransport",
                side_effect=lambda **kwargs: factory(handler),
            ),
        ):
            item = await files.download_file(
                FileInput(
                    download_url=URL,
                    file_id="file_1",
                    file_name="original.pdf",
                    mime_type="application/pdf",
                ),
                max_bytes=len(raw),
            )
        self.assertEqual(item, ("original.pdf", raw, "application/pdf"))
        self.assertEqual(requests[0].url.host, "8.8.8.8")
        self.assertEqual(requests[0].headers["host"], "files.oaiusercontent.com")
        self.assertEqual(
            requests[0].extensions["sni_hostname"], "files.oaiusercontent.com"
        )
        self.assertNotIn("authorization", requests[0].headers)
        self.assertNotIn("cookie", requests[0].headers)
        self.assertEqual(requests[0].headers["accept-encoding"], "identity")

    async def test_invalid_hosts_and_filenames_are_rejected_before_network(self):
        from quollnet_mcp.qledger.files import download_file
        from quollnet_mcp.qledger.models import FileInput

        for url in [
            "http://files.oaiusercontent.com/x",
            "https://evil.test/x",
            "https://files.oaiusercontent.com.evil.test/x",
            "https://127.0.0.1/x",
            "https://user:pass@files.oaiusercontent.com/x",
            "https://files.oaiusercontent.com:444/x",
            "https://files.oaiusercontent.com/x#frag",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                await download_file(
                    FileInput(download_url=url, file_id="f"), max_bytes=20
                )
        for name in ["../x", "a/b", "a\\b", "\r\nx", ".", ".."]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                await download_file(
                    FileInput(download_url=URL, file_id="f", filename=name),
                    max_bytes=20,
                )

    async def test_redirect_overflow_and_remote_errors_do_not_expose_signed_url(self):
        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.models import FileInput

        factory = httpx.MockTransport
        for response in [
            httpx.Response(302, headers={"location": "https://evil.test"}),
            httpx.Response(403, text="secret=redact"),
            httpx.Response(200, content=b"1234"),
            httpx.Response(200, content=b""),
            httpx.Response(200, content=b"1234", headers={"content-length": "4"}),
        ]:
            with (
                self.subTest(status=response.status_code),
                patch.object(
                    files, "resolve_public_addresses", return_value=["8.8.8.8"]
                ),
                patch.object(
                    files.httpx,
                    "AsyncHTTPTransport",
                    side_effect=lambda response=response, **kwargs: factory(
                        lambda request: response
                    ),
                ),
            ):
                with self.assertRaises(ValueError) as caught:
                    await files.download_file(
                        FileInput(download_url=URL, file_id="f"), max_bytes=3
                    )
                self.assertNotIn("redact", str(caught.exception))
                self.assertNotIn(URL, str(caught.exception))

    async def test_dns_rejects_any_nonpublic_address(self):
        from quollnet_mcp.qledger.files import resolve_public_addresses

        for ip in [
            "127.0.0.1",
            "10.0.0.1",
            "169.254.169.254",
            "::1",
            "::ffff:127.0.0.1",
            "224.0.0.1",
            "ff02::1",
        ]:
            with (
                self.subTest(ip=ip),
                patch(
                    "socket.getaddrinfo",
                    return_value=[
                        (2, 1, 6, "", ("8.8.8.8", 443)),
                        (2, 1, 6, "", (ip, 443)),
                    ],
                ),
                self.assertRaises(ValueError),
            ):
                await resolve_public_addresses("files.oaiusercontent.com")


class DocumentWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_share_revoke_relation_and_issue_backend_contracts(self):
        from quollnet_mcp.qledger.models import AttachmentQuery, AttachmentShareRequest
        from quollnet_mcp.qledger.models_documents import DocumentIssueRequest
        from quollnet_mcp.qledger.tools import attachments, documents

        seen = []
        expected = {
            "record_id": R,
            "attachment_id": A,
            "protected_url": "/protected",
            "verification_url": "/verify",
            "status": "issued",
        }

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=expected)

        async with client(handler) as c:
            with (
                patch.object(attachments, "qledger_client", c),
                patch.object(documents, "qledger_client", c),
                patch(
                    "quollnet_mcp.qledger.tools.common.auth.unit_token",
                    return_value="unit",
                ),
            ):
                await attachments.list_qledger_attachments(
                    U,
                    AttachmentQuery(
                        linked_to_object="record",
                        linked_to_object_id=R,
                        relation="issued_pdf",
                    ),
                )
                self.assertEqual(seen[-1].url.params["relation"], "issued_pdf")
                await attachments.create_qledger_attachment_share(
                    U, A, AttachmentShareRequest()
                )
                self.assertEqual(json.loads(seen[-1].content), {"expires_in": 3600})
                self.assertEqual(
                    seen[-1].url.path, f"/api/units/{U}/attachments/{A}/share"
                )
                await attachments.revoke_qledger_attachment_share(U, A, R)
                self.assertEqual(
                    (seen[-1].method, seen[-1].url.path),
                    ("DELETE", f"/api/units/{U}/attachments/{A}/shares/{R}"),
                )
                result = await documents.issue_qledger_record(
                    U,
                    R,
                    DocumentIssueRequest(
                        version=2,
                        filename="invoice.pdf",
                        reviewed_records={R: 2},
                        reviewed_attachments={A: "hash"},
                    ),
                    "stable",
                )
                self.assertEqual(result, expected)
                self.assertEqual(seen[-1].url.path, f"/api/units/{U}/records/{R}/issue")
                self.assertEqual(seen[-1].headers["Idempotency-Key"], "stable")
                self.assertEqual(
                    json.loads(seen[-1].content)["reviewed_attachments"], {A: "hash"}
                )
        for expiry in [59, 604801]:
            with self.assertRaises(ValueError):
                AttachmentShareRequest(expires_in=expiry)

    async def test_saved_preview_defaults_to_metadata_without_binary_transfer(self):
        from quollnet_mcp.qledger.models_documents import PdfRenderRequest
        from quollnet_mcp.qledger.tools import documents

        seen = []
        expected = {
            "attachment_id": A,
            "relation": "draft_pdf",
            "protected_url": "/protected",
            "status": "draft",
        }

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=expected)

        async with client(handler) as c:
            with (
                patch.object(documents, "qledger_client", c),
                patch.object(documents.auth, "unit_token", return_value="unit"),
            ):
                result = await documents.render_qledger_record_pdf(
                    U, R, PdfRenderRequest(version=2, save_to_record=True), "key"
                )
        self.assertEqual(len(result.content), 1)
        self.assertEqual(json.loads(result.content[0].text), expected)
        self.assertEqual(json.loads(seen[-1].content)["response_mode"], "metadata")


class WorkflowGuidanceTests(unittest.TestCase):
    def test_issuance_evidence_defaults_and_issuer_snapshot(self):
        from quollnet_mcp.qledger.models_documents import DocumentIssueRequest

        request = DocumentIssueRequest(version=1, issuer_name="Example Issuer")
        self.assertEqual(request.reviewed_records, {})
        self.assertEqual(request.reviewed_attachments, {})
        self.assertEqual(request.issuer_name, "Example Issuer")

    def test_guidance_separates_preview_issuance_links_and_derivatives(self):
        from quollnet_mcp.qledger.instructions import QLEDGER_INSTRUCTIONS as guidance

        for concept in [
            "issue_qledger_record",
            "draft_pdf",
            "protected_url",
            "create_qledger_attachment_share",
            "fileParams",
            "source_attachment_id",
            "separate .txt attachment",
            "customer",
            "vendor",
            "contract",
            "numbering",
        ]:
            self.assertIn(concept, guidance)
        self.assertNotIn("Uploads use strict base64", guidance)


class FileForwardingTests(unittest.IsolatedAsyncioTestCase):
    async def test_download_then_multipart_preserves_original_and_hides_backend_token(
        self,
    ):
        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.models import FileInput, TargetRef
        from quollnet_mcp.qledger.tools import attachments

        raw = b"\x00\xff\r\noriginal image bytes\x00"
        download_requests = []
        backend_requests = []
        factory = httpx.MockTransport

        def download(request):
            download_requests.append(request)
            return httpx.Response(200, content=raw)

        def backend(request):
            backend_requests.append(request)
            return httpx.Response(201, json={"id": A})

        async with client(backend) as c:
            with (
                patch.object(attachments, "qledger_client", c),
                patch.object(
                    attachments.auth, "unit_token", return_value="backend-secret"
                ),
                patch.object(
                    files, "resolve_public_addresses", return_value=["8.8.8.8"]
                ),
                patch.object(
                    files.httpx,
                    "AsyncHTTPTransport",
                    side_effect=lambda **kwargs: factory(download),
                ),
            ):
                result = await attachments.upload_qledger_attachment(
                    U,
                    TargetRef(linked_to_object="record", linked_to_object_id=R),
                    FileInput(
                        download_url=URL,
                        file_id="file_1",
                        file_name="scan.png",
                        mime_type="image/png",
                    ),
                    "stable",
                )
        self.assertEqual(result, {"id": A})
        self.assertEqual(len(backend_requests), 1)
        self.assertIn(raw, backend_requests[0].content)
        self.assertIn(b'filename="scan.png"', backend_requests[0].content)
        self.assertEqual(
            backend_requests[0].headers["authorization"], "Bearer backend-secret"
        )
        self.assertNotIn("backend-secret", str(download_requests[0].headers))
        self.assertNotIn(URL.encode(), backend_requests[0].content)

    async def test_unavailable_source_never_creates_backend_attachment(self):
        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.models import FileInput, TargetRef
        from quollnet_mcp.qledger.tools import attachments

        factory = httpx.MockTransport
        backend_requests = []
        async with client(lambda request: backend_requests.append(request)) as c:
            with (
                patch.object(attachments, "qledger_client", c),
                patch.object(
                    files, "resolve_public_addresses", return_value=["8.8.8.8"]
                ),
                patch.object(
                    files.httpx,
                    "AsyncHTTPTransport",
                    side_effect=lambda **kwargs: factory(
                        lambda request: httpx.Response(403)
                    ),
                ),
                self.assertRaises(ValueError),
            ):
                await attachments.upload_qledger_attachment(
                    U,
                    TargetRef(linked_to_object="record", linked_to_object_id=R),
                    FileInput(download_url=URL, file_id="file_1"),
                    "stable",
                )
        self.assertEqual(backend_requests, [])

    async def test_socket_failure_is_safe_and_binary_render_is_explicit(self):
        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.models import FileInput
        from quollnet_mcp.qledger.models_documents import PdfRenderRequest
        from quollnet_mcp.qledger.tools import documents

        factory = httpx.MockTransport

        def fail(request):
            raise httpx.ReadError("signed secret=redact", request=request)

        with (
            patch.object(files, "resolve_public_addresses", return_value=["8.8.8.8"]),
            patch.object(
                files.httpx,
                "AsyncHTTPTransport",
                side_effect=lambda **kwargs: factory(fail),
            ),
            self.assertRaises(ValueError) as caught,
        ):
            await files.download_file(
                FileInput(download_url=URL, file_id="file_1"), max_bytes=100
            )
        self.assertNotIn("redact", str(caught.exception))
        with self.assertRaisesRegex(ValueError, "save_to_record"):
            await documents.render_qledger_record_pdf(
                U, R, PdfRenderRequest(version=1, response_mode="metadata")
            )


class DownloadLoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_signed_download_url_is_not_logged(self):
        import logging

        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.models import FileInput

        factory = httpx.MockTransport
        with (
            patch.object(files, "resolve_public_addresses", return_value=["8.8.8.8"]),
            patch.object(
                files.httpx,
                "AsyncHTTPTransport",
                side_effect=lambda **kwargs: factory(
                    lambda request: httpx.Response(200, content=b"file")
                ),
            ),
            self.assertLogs("httpx", level="INFO") as logs,
        ):
            await files.download_file(
                FileInput(download_url=URL, file_id="file_1"), max_bytes=10
            )
            logging.getLogger("httpx").info("download test complete")
        self.assertNotIn("redact", " ".join(logs.output))


class IssuedDocumentMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_historical_document_and_status_have_separate_metadata_contracts(
        self,
    ):
        from quollnet_mcp.qledger.models_documents import DocumentStatusRequest
        from quollnet_mcp.qledger.tools import documents

        seen = []
        expected = {
            "record_id": R,
            "attachment_id": A,
            "protected_url": "/protected",
            "verification_url": "/verify",
            "status": "issued",
        }

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=expected)

        async with client(handler) as c:
            with (
                patch.object(documents, "qledger_client", c),
                patch.object(documents.auth, "unit_token", return_value="unit"),
            ):
                result = await documents.get_qledger_issued_document(U, R)
                self.assertEqual(result, expected)
                self.assertEqual(
                    (seen[-1].method, seen[-1].url.path),
                    ("GET", f"/api/units/{U}/records/{R}/document"),
                )
                await documents.update_qledger_document_status(
                    U,
                    R,
                    DocumentStatusRequest(
                        version=2,
                        status="superseded",
                        reason="Replaced by revised invoice",
                    ),
                )
                self.assertEqual(
                    (seen[-1].method, seen[-1].url.path),
                    ("POST", f"/api/units/{U}/records/{R}/document-status"),
                )
                self.assertEqual(
                    json.loads(seen[-1].content),
                    {
                        "version": 2,
                        "status": "superseded",
                        "reason": "Replaced by revised invoice",
                    },
                )
        for status in ["issued", "draft"]:
            with self.assertRaises(ValueError):
                DocumentStatusRequest(version=1, status=status, reason="reason")


class FileArgumentValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_sdk_validation_omits_signed_urls_for_upload_and_atomic_files(self):
        from mcp.server.mcpserver.exceptions import ToolError

        from quollnet_mcp.qledger.server import build_qledger_server

        server = build_qledger_server(settings())
        secret = "secr3t"
        file = {"download_url": "https://files.oaiusercontent.com/a?sig=" + secret}
        parent = {"linked_to_object": "record", "linked_to_object_id": R}
        calls = [
            (
                "upload_qledger_attachment",
                {
                    "unit_id": U,
                    "parent": parent,
                    "file": file,
                    "idempotency_key": "key",
                },
            ),
            (
                "execute_qledger_operation",
                {
                    "unit_id": U,
                    "operation": {
                        "attachments": [{"key": "scan", "file_field": "scan"}]
                    },
                    "files": [file],
                    "idempotency_key": "key",
                },
            ),
            (
                "upload_qledger_attachment",
                {
                    "parent": parent,
                    "file": {**file, "file_id": "file_1"},
                    "idempotency_key": "key",
                },
            ),
        ]
        for tool, arguments in calls:
            with (
                self.subTest(tool=tool, missing_unit="unit_id" not in arguments),
                self.assertRaises(ToolError) as caught,
            ):
                await server.call_tool(tool, arguments)
            self.assertNotIn(secret, str(caught.exception))
            self.assertNotIn("input_value", str(caught.exception))
            self.assertIn("Field required", str(caught.exception))

    async def test_sdk_file_value_errors_do_not_echo_url_or_filename(self):
        from mcp.server.mcpserver.exceptions import ToolError

        from quollnet_mcp.qledger.server import build_qledger_server

        server = build_qledger_server(settings())
        parent = {"linked_to_object": "record", "linked_to_object_id": R}
        for file in [
            {
                "download_url": "https://files.oaiusercontent.com/a?sig=secr3t",
                "file_id": "file_1",
                "mime_type": "invalid/secr3t;",
            },
            {"download_url": "https://evil.test/a?sig=secr3t", "file_id": "file_1"},
            {
                "download_url": "https://files.oaiusercontent.com/a?sig=secr3t",
                "file_id": "file_1",
                "filename": "../secr3t.pdf",
            },
        ]:
            with self.subTest(file=file), self.assertRaises(ToolError) as caught:
                await server.call_tool(
                    "upload_qledger_attachment",
                    {
                        "unit_id": U,
                        "parent": parent,
                        "file": file,
                        "idempotency_key": "key",
                    },
                )
            self.assertNotIn("secr3t", str(caught.exception))
            self.assertNotIn("input_value", str(caught.exception))

    def test_relations_are_open_vocabulary_and_status_is_authoritative(self):
        from quollnet_mcp.qledger.instructions import QLEDGER_INSTRUCTIONS

        self.assertIn("relation labels remain caller-defined", QLEDGER_INSTRUCTIONS)
        self.assertNotIn("reserved draft_pdf", QLEDGER_INSTRUCTIONS)
        self.assertIn("authoritative issuance status", QLEDGER_INSTRUCTIONS)


class DownloadMimeInferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_or_generic_mime_uses_response_then_filename(self):
        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.models import FileInput

        cases = [
            ({"file_name": "logo.png"}, "image/png; charset=binary", "image/png"),
            ({"file_name": "scan.pdf"}, None, "application/pdf"),
            ({"file_name": "logo.png"}, "application/octet-stream", "image/png"),
            ({"file_name": "scan.pdf"}, "invalid content type", "application/pdf"),
            (
                {"file_name": "source.unknown-extension"},
                None,
                "application/octet-stream",
            ),
            (
                {"file_name": "logo.png", "mime_type": "application/octet-stream"},
                "image/png",
                "image/png",
            ),
            (
                {"file_name": "logo.jpg", "mime_type": "image/jpeg"},
                "image/png",
                "image/jpeg",
            ),
        ]
        for metadata, response_mime, expected in cases:
            headers = {"content-type": response_mime} if response_mime else {}
            response = httpx.Response(200, content=b"original bytes", headers=headers)
            with (
                self.subTest(metadata=metadata, response_mime=response_mime),
                patch.object(
                    files, "resolve_public_addresses", return_value=["8.8.8.8"]
                ),
                patch.object(
                    files.httpx,
                    "AsyncHTTPTransport",
                    side_effect=lambda response=response, **kwargs: httpx.MockTransport(
                        lambda request: response
                    ),
                ),
            ):
                downloaded = await files.download_file(
                    FileInput(download_url=URL, file_id="file_1", **metadata),
                    max_bytes=100,
                )
            self.assertEqual(downloaded[1], b"original bytes")
            self.assertEqual(downloaded[2], expected)
