"""QEntries-authorized printing through its QTypeset adapter; no local PDF engine."""

import base64
import hashlib
import json
from uuid import UUID

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import (
    BlobResourceContents,
    CallToolResult,
    EmbeddedResource,
    TextContent,
)

from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger import auth
from quollnet_mcp.qledger.models import api_payload
from quollnet_mcp.qledger.models_documents import (
    DocumentIssueRequest,
    DocumentStatusRequest,
    PdfRenderRequest,
)
from quollnet_mcp.qledger.qledger_client import QledgerClientError

from .common import call, object_id, unit_path


async def get_qledger_document_design_guidance(
    unit_id: UUID, include_schema: bool = False
):
    # Query is intentionally explicit: the full contract is loaded only on demand.
    token = await auth.unit_token(unit_id)
    try:
        return await qledger_client.request(
            "GET",
            unit_path(unit_id) + "/document-design-guidance",
            access_token=token,
            params={"include_schema": str(include_schema).lower()},
        )
    except QledgerClientError as error:
        raise ToolError(str(error)) from None


async def render_qledger_record_pdf(
    unit_id: UUID,
    record_id: UUID,
    request: PdfRenderRequest,
    idempotency_key: str | None = None,
) -> CallToolResult:
    if request.save_to_record and not idempotency_key:
        raise ValueError("Saving the draft PDF requires a stable idempotency_key")
    mode = request.response_mode or ("metadata" if request.save_to_record else "binary")
    if mode == "metadata" and not request.save_to_record:
        raise ValueError("Metadata response requires save_to_record=true")
    payload = api_payload(request)
    payload["response_mode"] = mode
    token = await auth.unit_token(unit_id)
    try:
        if mode == "metadata":
            metadata = await qledger_client.request(
                "POST",
                unit_path(unit_id) + "/records/" + object_id(record_id) + "/pdf",
                access_token=token,
                payload=payload,
                idempotency_key=idempotency_key,
            )
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(metadata))]
            )
        content, attachment_id = await qledger_client.render_pdf(
            unit_path(unit_id) + "/records/" + object_id(record_id) + "/pdf",
            access_token=token,
            payload=payload,
            idempotency_key=idempotency_key,
            max_bytes=min(qledger_client.settings.qledger_max_file_bytes, 8_000_000),
        )
    except QledgerClientError as error:
        raise ToolError(str(error)) from None
    digest = hashlib.sha256(content).hexdigest()
    uri = (
        f"qledger://units/{object_id(unit_id)}/attachments/{attachment_id}"
        if attachment_id
        else f"qledger://rendered/{digest}"
    )
    metadata = {
        "record_id": object_id(record_id),
        "record_version": request.version,
        "filename": request.filename,
        "content_type": "application/pdf",
        "size_bytes": len(content),
        "sha256": digest,
        "saved_to_record": bool(attachment_id),
        "attachment_id": attachment_id,
    }
    return CallToolResult(
        content=[
            TextContent(type="text", text=json.dumps(metadata)),
            EmbeddedResource(
                resource=BlobResourceContents(
                    uri=uri,
                    mime_type="application/pdf",
                    blob=base64.b64encode(content).decode("ascii"),
                )
            ),
        ]
    )


async def issue_qledger_record(
    unit_id: UUID, record_id: UUID, request: DocumentIssueRequest, idempotency_key: str
):
    return await call(
        qledger_client,
        "POST",
        unit_path(unit_id) + "/records/" + object_id(record_id) + "/issue",
        unit_id=unit_id,
        body=request,
        key=idempotency_key,
    )


async def get_qledger_issued_document(unit_id: UUID, record_id: UUID):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/records/" + object_id(record_id) + "/document",
        unit_id=unit_id,
    )


async def update_qledger_document_status(
    unit_id: UUID, record_id: UUID, request: DocumentStatusRequest
):
    return await call(
        qledger_client,
        "POST",
        unit_path(unit_id) + "/records/" + object_id(record_id) + "/document-status",
        unit_id=unit_id,
        body=request,
    )
