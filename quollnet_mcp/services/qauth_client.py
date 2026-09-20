from collections.abc import Mapping
from types import TracebackType
from typing import Any

import httpx

from quollnet_mcp.config import Settings, get_settings


class QAuthClientError(Exception):
    """Raised when QAuth cannot exchange the MCP identity for an app token."""


class QAuthClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "QAuthClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.qauth_issuer_url,
                timeout=self.settings.qauth_timeout_seconds,
                headers={"User-Agent": f"quollnet-mcp/{self.settings.service_version}"},
            )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def exchange_app_token(
        self,
        *,
        mcp_access_token: str,
        target_app_id: str,
    ) -> str:
        """Exchange a Quollnet MCP token for a normal target-app user token."""
        if self._client is None:
            raise QAuthClientError(
                "QAuthClient must be used as an async context manager"
            )

        try:
            response = await self._client.post(
                "/oauth/exchange-app-token",
                json={"target_app_id": target_app_id},
                headers={"Authorization": f"Bearer {mcp_access_token}"},
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as error:
            detail = None
            try:
                body = error.response.json()
                if isinstance(body, Mapping):
                    candidate = body.get("error_description") or body.get("error")
                    if isinstance(candidate, str) and candidate.strip():
                        detail = candidate.strip()
            except ValueError:
                pass
            message = f"QAuth returned HTTP {error.response.status_code}"
            if detail:
                message = f"{message}: {detail}"
            raise QAuthClientError(message) from error
        except httpx.RequestError as error:
            raise QAuthClientError("QAuth request failed") from error
        except ValueError as error:
            raise QAuthClientError("QAuth returned invalid JSON") from error

        token = data.get("access_token") if isinstance(data, Mapping) else None
        if not isinstance(token, str) or not token:
            raise QAuthClientError("QAuth response did not include an access token")
        return token
