import urllib.parse
from collections.abc import Mapping
from types import TracebackType
from typing import Any

import httpx

from quollnet_mcp.config import Settings, get_settings


class QFlowClientError(Exception):
    """Raised when the q_flow backend cannot complete a CashflowPot request."""


class QFlowClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "QFlowClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.qflow_base_url,
                timeout=self.settings.qflow_timeout_seconds,
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

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        params: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        if self._client is None:
            raise QFlowClientError(
                "QFlowClient must be used as an async context manager"
            )

        try:
            response = await self._client.request(
                method,
                path,
                params=params,
                json=dict(payload) if payload is not None else None,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            detail = None
            try:
                body = error.response.json()
                if isinstance(body, Mapping):
                    candidate = body.get("message") or body.get("error")
                    if isinstance(candidate, str) and candidate.strip():
                        detail = candidate.strip()
            except ValueError:
                pass
            message = f"q_flow returned HTTP {error.response.status_code}"
            if detail:
                message = f"{message}: {detail}"
            raise QFlowClientError(message) from error
        except httpx.RequestError as error:
            raise QFlowClientError("q_flow request failed") from error
        except ValueError as error:
            raise QFlowClientError("q_flow returned invalid JSON") from error

    async def list_projects(
        self,
        *,
        access_token: str,
        page: int = 1,
        per_page: int = 25,
    ) -> Any:
        return await self._request_json(
            "GET",
            "/projects",
            access_token=access_token,
            params={"page": page, "per_page": per_page},
        )

    async def import_cashflow(
        self,
        *,
        access_token: str,
        unit_id: str,
        payload: Mapping[str, Any],
    ) -> Any:
        safe_unit_id = urllib.parse.quote(unit_id, safe="")
        return await self._request_json(
            "POST",
            f"/project/{safe_unit_id}/cashflows/import",
            access_token=access_token,
            payload=payload,
        )
