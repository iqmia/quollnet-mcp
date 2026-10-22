"""A combined operation is always exactly one QLedger request."""

import json
from typing import Any
from uuid import UUID

from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger import auth
from quollnet_mcp.qledger.files import download_file
from quollnet_mcp.qledger.models import FileInput, api_payload, validate_idempotency_key
from quollnet_mcp.qledger.models_records import OperationRequest
from quollnet_mcp.qledger.qledger_client import QledgerClientError

from .common import unit_path


async def execute_qledger_operation(
    unit_id: UUID,
    operation: OperationRequest,
    idempotency_key: str,
    files: list[FileInput] | None = None,
) -> dict[str, Any]:
    path = unit_path(unit_id) + "/operations"
    key = validate_idempotency_key(idempotency_key)
    files = files or []
    if len(files) != len(operation.attachments):
        raise ValueError(
            "Supply one file per operation.attachments entry in the same order"
        )
    settings = qledger_client.settings
    decoded = {}
    total = 0
    for attachment, file in zip(operation.attachments, files, strict=True):
        remaining = settings.qledger_max_batch_file_bytes - total
        item = await download_file(
            file, max_bytes=min(settings.qledger_max_file_bytes, remaining)
        )
        total += len(item[1])
        decoded[attachment.file_field] = item
    payload = api_payload(operation)
    token = await auth.unit_token(unit_id)
    try:
        if decoded:
            return await qledger_client.multipart(
                path,
                access_token=token,
                fields={"payload": json.dumps(payload, allow_nan=False)},
                files=decoded,
                idempotency_key=key,
            )
        return await qledger_client.request(
            "POST", path, access_token=token, payload=payload, idempotency_key=key
        )
    except QledgerClientError as error:
        raise ToolError(str(error)) from None
