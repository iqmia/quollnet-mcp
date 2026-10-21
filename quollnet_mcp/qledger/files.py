"""Original-byte transfer with request-time authorization and explicit bounds."""

import base64
import binascii
from uuid import UUID
from mcp.types import BlobResourceContents
from mcp.server.mcpserver.exceptions import ToolError
from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger import auth
from quollnet_mcp.qledger.models import FileInput
from quollnet_mcp.qledger.qledger_client import QledgerClientError
from .tools.common import unit_path, object_id


def decode_file(file: FileInput, *, max_bytes: int) -> tuple[str, bytes, str]:
    name = file.filename
    if (
        name in (".", "..")
        or any(c in name for c in "/\\")
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
    ):
        raise ValueError("Supply a safe filename without paths or control characters")
    if len(file.file_base64) > 4 * ((max_bytes + 2) // 3):
        raise ValueError("File exceeds the configured transfer limit")
    try:
        value = base64.b64decode(file.file_base64, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError(
            "Invalid base64 file content; supply raw base64 without a data-URI prefix"
        ) from None
    if not value or len(value) > max_bytes:
        raise ValueError("File is empty or exceeds the configured transfer limit")
    return name, value, file.content_type


async def attachment_resource(
    unit_id: UUID, attachment_id: UUID
) -> BlobResourceContents:
    unit_id = object_id(unit_id)
    attachment_id = object_id(attachment_id)
    token = await auth.unit_token(UUID(unit_id))
    try:
        content, mime = await qledger_client.download(
            unit_path(unit_id) + "/attachments/" + attachment_id + "/download",
            access_token=token,
            max_bytes=qledger_client.settings.qledger_max_file_bytes,
        )
    except QledgerClientError as error:
        raise ToolError(str(error)) from None
    return BlobResourceContents(
        uri=f"qledger://units/{unit_id}/attachments/{attachment_id}",
        mime_type=mime,
        blob=base64.b64encode(content).decode("ascii"),
    )
