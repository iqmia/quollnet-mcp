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

    # Search articles tool
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
        params = {
            name: value
            for name, value in {
                "q": q,
                "topic": topic,
                "lang": lang,
                "status": status,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
                "page": page,
                "per_page": per_page,
            }.items()
            if value is not None
        }

        return await self.get_json(
            "/articles/api/v1/articles/catalog",
            params=params,
            access_token=access_token,
        )
    
    async def post_json(
        self,
        path: str,
        payload: Mapping[str, Any],
        access_token: str | None = None,
    ) -> Any:
        """POST a JSON payload to qApp and return its JSON response."""
        if self._client is None:
            raise QAppClientError(
                "QAppClient must be used as an async context manager"
            )

        headers = (
            {"Authorization": f"Bearer {access_token}"}
            if access_token
            else None
        )

        try:
            response = await self._client.post(
                path,
                json=dict(payload),
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as error:
            detail = None

            try:
                response_data = error.response.json()
                if isinstance(response_data, Mapping):
                    candidate = (
                        response_data.get("message")
                        or response_data.get("error")
                    )
                    if isinstance(candidate, str) and candidate.strip():
                        detail = candidate.strip()
            except ValueError:
                pass

            message = (
                f"qApp returned HTTP {error.response.status_code}"
            )
            if detail:
                message = f"{message}: {detail}"

            raise QAppClientError(message) from error

        except httpx.RequestError as error:
            raise QAppClientError("qApp request failed") from error

        except ValueError as error:
            raise QAppClientError(
                "qApp returned invalid JSON"
            ) from error

    async def patch_json(
        self,
        path: str,
        payload: Mapping[str, Any],
        access_token: str | None = None,
    ) -> Any:
        """PATCH a JSON payload to qApp and return its JSON response."""
        if self._client is None:
            raise QAppClientError(
                "QAppClient must be used as an async context manager"
            )

        headers = (
            {"Authorization": f"Bearer {access_token}"}
            if access_token
            else None
        )

        try:
            response = await self._client.patch(
                path,
                json=dict(payload),
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as error:
            detail = None

            try:
                response_data = error.response.json()
                if isinstance(response_data, Mapping):
                    candidate = (
                        response_data.get("message")
                        or response_data.get("error")
                    )
                    if isinstance(candidate, str) and candidate.strip():
                        detail = candidate.strip()
            except ValueError:
                pass

            message = f"qApp returned HTTP {error.response.status_code}"
            if detail:
                message = f"{message}: {detail}"

            raise QAppClientError(message) from error

        except httpx.RequestError as error:
            raise QAppClientError("qApp request failed") from error

        except ValueError as error:
            raise QAppClientError("qApp returned invalid JSON") from error

    # Create article draft tool
    async def create_article_draft(
        self,
        *,
        access_token: str,
        payload: Mapping[str, Any],
    ) -> Any:
        """Create an unpublished article draft through qApp."""
        return await self.post_json(
            "/articles/api/v1/articles/drafts",
            payload=payload,
            access_token=access_token,
        )

    async def get_internal_link_candidates(
        self,
        *,
        access_token: str,
        text: str,
        top_n: int = 10,
        exclude_slugs: list[str] | None = None,
    ) -> Any:
        """Return internal-link candidates from qApp for the given text."""
        return await self.post_json(
            "/articles/api/v1/articles/internal-link-candidates",
            payload={
                "text": text,
                "top_n": top_n,
                "exclude_slugs": exclude_slugs or [],
            },
            access_token=access_token,
        )

    async def get_article_authoring_policy(
        self,
        *,
        access_token: str,
    ) -> Any:
        """Retrieve the current article-authoring policy from qApp."""
        return await self.get_json(
            "/articles/api/v1/articles/authoring-policy",
            access_token=access_token,
        )

    # Get article tool
    async def get_article(
        self,
        *,
        access_token: str,
        article_id: str,
    ) -> Any:
        """Retrieve a single article by ID from qApp."""
        return await self.get_json(
            f"/articles/api/v1/articles/{article_id}",
            access_token=access_token,
        )

    # Edit article draft tool
    async def edit_article_draft(
        self,
        *,
        access_token: str,
        article_id: str,
        payload: Mapping[str, Any],
    ) -> Any:
        """PATCH an existing unpublished article draft through qApp."""
        return await self.patch_json(
            f"/articles/api/v1/articles/{article_id}",
            payload=payload,
            access_token=access_token,
        )