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
from quollnet_mcp.qledger.models_documents import PdfRenderRequest
from quollnet_mcp.qledger.qledger_client import QledgerClientError

from .common import object_id, unit_path


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
        raise ValueError("Saving the issued PDF requires a stable idempotency_key")
    token = await auth.unit_token(unit_id)
    try:
        content, attachment_id = await qledger_client.render_pdf(
            unit_path(unit_id) + "/records/" + object_id(record_id) + "/pdf",
            access_token=token,
            payload=api_payload(request),
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
