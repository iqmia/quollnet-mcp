"""Fixed-origin QLedger HTTP adapter. Mutations are never automatically retried."""

import re
from urllib.parse import urlsplit
import httpx
from quollnet_mcp.qledger.models import validate_idempotency_key


class QledgerClientError(Exception):
    def __init__(
        self, message: str, *, status: int | None = None, outcome_unknown: bool = False
    ):
        self.status = status
        self.outcome_unknown = outcome_unknown
        super().__init__(message)


def _safe_message(value, token: str) -> str:
    if not isinstance(value, str):
        return "Request rejected"
    value = value.replace(token, "[redacted]") if token else value
    value = re.sub(r"eyJ[A-Za-z0-9_\-.]+", "[redacted]", value)
    value = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", value)
    return " ".join(value.split())[:500]


class QledgerClient:
    def __init__(self, settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        if self._client is None:
            url = urlsplit(self.settings.qledger_base_url)
            if (
                url.scheme != "https"
                or not url.netloc
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError(
                    "QLEDGER_BASE_URL must be an HTTPS service URL without credentials/query/fragment"
                )
            self._client = httpx.AsyncClient(
                base_url=self.settings.qledger_base_url.rstrip("/") + "/",
                timeout=self.settings.qledger_timeout_seconds,
                follow_redirects=False,
                headers={"User-Agent": f"quollnet-mcp/{self.settings.service_version}"},
            )
        return self

    async def __aexit__(self, *args):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _path(self, path):
        if (
            not path.startswith("/api/")
            or "://" in path
            or "?" in path
            or "#" in path
            or "\\" in path
            or ".." in path.split("/")
        ):
            raise ValueError(
                "Only adapter-built relative QLedger API paths are allowed"
            )
        if self._client is None:
            raise QledgerClientError("QLedger client is not running")
        return path.lstrip("/")

    def _headers(self, token, key):
        result = {"Authorization": f"Bearer {token}"}
        if key is not None:
            result["Idempotency-Key"] = validate_idempotency_key(key)
        return result

    def _check(self, response, token, method="GET", key=None):
        if response.is_success:
            return
        if response.status_code >= 500 and method not in ("GET", "HEAD"):
            raise self._transport_error(
                method,
                key,
                message=f"QLedger HTTP {response.status_code}: service error.",
                status=response.status_code,
            )
        message = "Request rejected"
        try:
            body = response.json()
            if isinstance(body, dict):
                message = _safe_message(body.get("message"), token)
                detail = body.get("detail")
                if isinstance(detail, dict):
                    if isinstance(detail.get("code"), str):
                        message += " (" + _safe_message(detail["code"], token) + ")"
                    # APIFlask validation locations contain field -> message lists.
                    # Exclude input values, arbitrary extra detail and credential fields.
                    errors = []
                    for location in ("json", "query", "files", "form"):
                        fields = detail.get(location)
                        if not isinstance(fields, dict):
                            continue
                        for field, messages in list(fields.items())[:10]:
                            if not isinstance(field, str) or not re.fullmatch(
                                r"[A-Za-z0-9_.\[\]-]{1,100}", field
                            ):
                                continue
                            if re.search(
                                r"token|password|secret|authorization", field, re.I
                            ):
                                continue
                            if isinstance(messages, list):
                                for item in messages[:3]:
                                    if isinstance(item, str):
                                        errors.append(
                                            field + ": " + _safe_message(item, token)
                                        )
                    if errors:
                        message += " — " + "; ".join(errors)[:2000]
        except ValueError:
            pass
        guidance = ""
        if response.status_code == 409:
            guidance = " Reload and review changes; do not replace reviewed versions or evidence automatically."
        elif response.status_code == 401:
            guidance = " Reconnect or obtain a fresh token; no mutation was automatically retried."
        raise QledgerClientError(
            f"QLedger HTTP {response.status_code}: {message}.{guidance}",
            status=response.status_code,
        )

    def _transport_error(
        self, method, key, *, message="QLedger transport failed.", status=None
    ):
        unknown = method not in ("GET", "HEAD")
        guidance = ""
        if unknown:
            guidance = (
                " Outcome unknown. Retry with the same idempotency key, payload and file bytes."
                if key
                else " Outcome unknown. Inspect state before resubmitting this unkeyed mutation."
            )
        return QledgerClientError(
            message + guidance, outcome_unknown=unknown, status=status
        )

    async def request(
        self,
        method,
        path,
        *,
        access_token,
        params=None,
        payload=None,
        idempotency_key=None,
    ):
        path = self._path(path)
        try:
            response = await self._client.request(
                method,
                path,
                params={k: v for k, v in (params or {}).items() if v is not None},
                json=payload,
                headers=self._headers(access_token, idempotency_key),
            )
        except httpx.RequestError:
            raise self._transport_error(method, idempotency_key) from None
        self._check(response, access_token, method, idempotency_key)
        if response.status_code == 204:
            return None
        try:
            value = response.json()
            if not isinstance(value, (dict, list)):
                raise ValueError()
            return value
        except ValueError:
            raise self._transport_error(
                method,
                idempotency_key,
                message="QLedger returned invalid JSON.",
                status=response.status_code,
            ) from None

    async def multipart(self, path, *, access_token, fields, files, idempotency_key):
        path = self._path(path)
        try:
            response = await self._client.post(
                path,
                data=fields,
                files=files,
                headers=self._headers(access_token, idempotency_key),
            )
        except httpx.RequestError:
            raise self._transport_error("POST", idempotency_key) from None
        self._check(response, access_token, "POST", idempotency_key)
        try:
            value = response.json()
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except ValueError:
            raise self._transport_error(
                "POST",
                idempotency_key,
                message="QLedger returned invalid JSON.",
                status=response.status_code,
            ) from None

    async def download(self, path, *, access_token, max_bytes):
        path = self._path(path)
        try:
            async with self._client.stream(
                "GET", path, headers=self._headers(access_token, None)
            ) as response:
                size = 0
                chunks = []
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise QledgerClientError(
                            "Attachment exceeds the configured transfer limit"
                        )
                    chunks.append(chunk)
                content = b"".join(chunks)
                if not response.is_success:
                    self._check(
                        httpx.Response(response.status_code, content=content),
                        access_token,
                    )
                return content, response.headers.get(
                    "content-type", "application/octet-stream"
                ).split(";")[0]
        except httpx.RequestError:
            raise self._transport_error("GET", None) from None
