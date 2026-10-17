import json
import re
from uuid import UUID
from mcp.types import CallToolResult, EmbeddedResource, TextContent
from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger import auth
from quollnet_mcp.qledger.models import (
    FileInput,
    TargetRef,
    AttachmentQuery,
    api_payload,
)
from quollnet_mcp.qledger.files import decode_file, attachment_resource
from quollnet_mcp.qledger.qledger_client import QledgerClientError
from .common import call, unit_path, object_id


def _attachment(unit_id, attachment_id):
    return unit_path(unit_id) + "/attachments/" + object_id(attachment_id)


async def list_qledger_attachments(unit_id: UUID, query: AttachmentQuery):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/attachments",
        unit_id=unit_id,
        query=query,
    )


async def get_qledger_attachment(unit_id: UUID, attachment_id: UUID):
    return await call(
        qledger_client, "GET", _attachment(unit_id, attachment_id), unit_id=unit_id
    )


async def upload_qledger_attachment(
    unit_id: UUID, parent: TargetRef, file: FileInput, idempotency_key: str
):
    path = unit_path(unit_id) + "/attachments"
    decoded = decode_file(
        file, max_bytes=qledger_client.settings.qledger_max_file_bytes
    )
    token = await auth.unit_token(unit_id)
    try:
        return await qledger_client.multipart(
            path,
            access_token=token,
            fields=api_payload(parent),
            files={"file": decoded},
            idempotency_key=idempotency_key,
        )
    except QledgerClientError as error:
        raise ToolError(str(error)) from None


async def download_qledger_attachment(
    unit_id: UUID, attachment_id: UUID
) -> CallToolResult:
    metadata = await get_qledger_attachment(unit_id, attachment_id)
    resource = await attachment_resource(unit_id, attachment_id)
    # QLedger deliberately downloads with octet-stream; its stored metadata
    # identifies the original file type for clients that render binary resources.
    mime = metadata.get("content_type")
    resource.mime_type = (
        mime
        if isinstance(mime, str)
        and re.fullmatch(r"[A-Za-z0-9!#$&^_.+\-]+/[A-Za-z0-9!#$&^_.+\-]+", mime)
        else "application/octet-stream"
    )
    safe_metadata = {
        k: metadata[k]
        for k in ("id", "original_filename", "content_type", "size_bytes", "sha256")
        if k in metadata
    }
    return CallToolResult(
        content=[
            TextContent(type="text", text=json.dumps(safe_metadata)),
            EmbeddedResource(resource=resource),
        ]
    )


async def list_qledger_attachment_links(unit_id: UUID, attachment_id: UUID):
    return await call(
        qledger_client,
        "GET",
        _attachment(unit_id, attachment_id) + "/links",
        unit_id=unit_id,
    )


async def link_qledger_attachment(
    unit_id: UUID, attachment_id: UUID, request: TargetRef, idempotency_key: str
):
    return await call(
        qledger_client,
        "POST",
        _attachment(unit_id, attachment_id) + "/links",
        unit_id=unit_id,
        body=request,
        key=idempotency_key,
    )


async def unlink_qledger_attachment(unit_id: UUID, attachment_id: UUID, link_id: UUID):
    return await call(
        qledger_client,
        "DELETE",
        _attachment(unit_id, attachment_id) + "/links/" + object_id(link_id),
        unit_id=unit_id,
    )


async def replace_qledger_attachment_link(
    unit_id: UUID, attachment_id: UUID, link_id: UUID, request: TargetRef
):
    return await call(
        qledger_client,
        "PATCH",
        _attachment(unit_id, attachment_id) + "/links/" + object_id(link_id),
        unit_id=unit_id,
        body=request,
    )
