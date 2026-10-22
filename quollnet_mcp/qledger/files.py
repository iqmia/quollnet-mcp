"""Original-byte transfer with request-time authorization and explicit bounds."""

import asyncio
import base64
import ipaddress
import mimetypes
import re
import socket
from uuid import UUID

import httpx
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import BlobResourceContents

from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger import auth
from quollnet_mcp.qledger.models import FileInput
from quollnet_mcp.qledger.qledger_client import QledgerClientError

from .tools.common import object_id, unit_path


def _safe_name(file: FileInput) -> str:
    name = file.file_name or file.filename or "upload.bin"
    if (
        name in (".", "..")
        or any(c in name for c in "/\\")
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
    ):
        raise ValueError("Supply a safe filename without paths or control characters")
    return name


async def resolve_public_addresses(host: str) -> list[str]:
    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM),
            timeout=10,
        )
        addresses = list(dict.fromkeys(result[4][0] for result in results))
        parsed = [ipaddress.ip_address(ip) for ip in addresses]
        if not parsed or any(
            not ip.is_global or ip.is_multicast or ip.is_reserved for ip in parsed
        ):
            raise ValueError()
        return addresses
    except (OSError, ValueError, TimeoutError):
        raise ValueError("File host must resolve only to public addresses") from None


def _file_url(value: str) -> httpx.URL:
    try:
        url = httpx.URL(value)
        host = url.host.lower()
        # Narrow host families used by ChatGPT's authorized file delivery. Never
        # accept arbitrary Azure/S3 tenants or arbitrary public HTTPS endpoints.
        allowed = (
            host == "files.oaiusercontent.com"
            or host.endswith(".oaiusercontent.com")
            or re.fullmatch(
                r"(?:oaisdmntpr|oaisdsorpr|sdmntpr)[a-z0-9-]*\.blob\.core\.windows\.net",
                host,
            )
            or re.fullmatch(
                r"oaisdmntpr[a-z0-9-]*aws\.s3\.[a-z0-9-]+\.amazonaws\.com", host
            )
        )
        if (
            url.scheme != "https"
            or not allowed
            or url.userinfo
            or url.port not in (None, 443)
            or url.fragment
        ):
            raise ValueError()
        return url
    except (ValueError, httpx.InvalidURL):
        raise ValueError(
            "Supply an HTTPS ChatGPT file download URL without credentials or redirects"
        ) from None


async def download_file(file: FileInput, *, max_bytes: int) -> tuple[str, bytes, str]:
    name = _safe_name(file)
    url = _file_url(file.download_url)
    addresses = await resolve_public_addresses(url.host)
    # Pin the checked address so a second DNS lookup cannot rebind to a private
    # address. Keep the original host for TLS verification/SNI and HTTP routing.
    target = url.copy_with(host=addresses[0])
    try:
        # A dedicated transport has no cookies, default credentials, environment
        # proxies, redirect policy or AsyncClient request logger (signed URLs are
        # secrets and must never appear in the normal HTTP client logs).
        async with httpx.AsyncHTTPTransport(trust_env=False, retries=0) as transport:
            request = httpx.Request(
                "GET",
                target,
                headers={"Host": url.host, "Accept-Encoding": "identity"},
                extensions={
                    "sni_hostname": url.host,
                    "timeout": {"connect": 10, "read": 30, "write": 30, "pool": 10},
                },
            )
            response = await transport.handle_async_request(request)
            try:
                if response.status_code != 200:
                    raise ValueError(
                        "File download failed; request a fresh authorized file reference"
                    )
                length = response.headers.get("content-length")
                if length is not None and (
                    not length.isdigit() or int(length) > max_bytes
                ):
                    raise ValueError("File exceeds the configured transfer limit")
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("File exceeds the configured transfer limit")
                    chunks.append(chunk)
                if not size:
                    raise ValueError("File is empty")
                mime = file.mime_type
                if mime.lower() == "application/octet-stream":
                    response_mime = (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if response_mime != "application/octet-stream" and re.fullmatch(
                        r"[A-Za-z0-9!#$&^_.+\-]+/[A-Za-z0-9!#$&^_.+\-]+", response_mime
                    ):
                        mime = response_mime
                    else:
                        mime = (
                            mimetypes.guess_type(name)[0] or "application/octet-stream"
                        )
                return name, b"".join(chunks), mime
            finally:
                await response.aclose()
    except httpx.HTTPError:
        # Never include signed URLs, upstream body text or credentials in errors.
        raise ValueError(
            "File download failed; request a fresh authorized file reference"
        ) from None


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
