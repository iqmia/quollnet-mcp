from collections.abc import Mapping
from types import TracebackType
from typing import Any

import httpx

from quollnet_mcp.config import Settings, get_settings


class QAppClientError(Exception):
    """Raised when the qApp HTTP client cannot return a JSON response."""


class QAppClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "QAppClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.qapp_base_url,
                timeout=self.settings.qapp_timeout_seconds,
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

    async def get_json(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        access_token: str | None = None,
    ) -> Any:
        if self._client is None:
            raise QAppClientError("QAppClient must be used as an async context manager")

        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
        try:
            response = await self._client.get(path, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            raise QAppClientError(
                f"qApp returned HTTP {error.response.status_code}"
            ) from error
        except httpx.RequestError as error:
            raise QAppClientError("qApp request failed") from error
        except ValueError as error:
            raise QAppClientError("qApp returned invalid JSON") from error

    async def search_articles(
        self,
        *,
        access_token: str,
        q: str | None = None,
        topic: str | None = None,
        lang: str | None = None,
        status: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
    ) -> Any:
        params: dict[str, Any] = {
            "q": q,
            "topic": topic,
            "lang": lang,
            "status": status,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "page": page,
            "per_page": per_page,
        }
        for parameter in ("q", "topic", "lang"):
            if params[parameter] is None:
                del params[parameter]

        return await self.get_json(
            "/articles/api/v1/articles/catalog",
            params=params,
            access_token=access_token,
        )
