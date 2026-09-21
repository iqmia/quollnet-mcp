import mimetypes
import urllib.parse
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

    @staticmethod
    def _http_error_message(error: httpx.HTTPStatusError) -> str:
        message = f"qApp returned HTTP {error.response.status_code}"

        try:
            payload = error.response.json()
        except ValueError:
            return message

        if not isinstance(payload, Mapping):
            return message

        detail = payload.get("message") or payload.get("error")
        if isinstance(detail, str) and detail.strip():
            message = f"{message}: {detail.strip()}"

        validation_errors = payload.get("errors")
        if isinstance(validation_errors, list):
            items = [
                str(item).strip()
                for item in validation_errors
                if str(item).strip()
            ]
            if items:
                message = f"{message}: {'; '.join(items)}"

        return message

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

    async def put_json(
        self,
        path: str,
        payload: Mapping[str, Any],
        access_token: str | None = None,
    ) -> Any:
        """PUT a JSON payload to qApp and return its JSON response."""
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
            response = await self._client.put(
                path,
                json=dict(payload),
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            raise QAppClientError(
                self._http_error_message(error)
            ) from error
        except httpx.RequestError as error:
            raise QAppClientError("qApp request failed") from error
        except ValueError as error:
            raise QAppClientError("qApp returned invalid JSON") from error

    async def delete_json(
        self,
        path: str,
        access_token: str | None = None,
    ) -> Any:
        """DELETE one qApp resource and return its JSON response."""
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
            response = await self._client.delete(
                path,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            raise QAppClientError(
                self._http_error_message(error)
            ) from error
        except httpx.RequestError as error:
            raise QAppClientError("qApp request failed") from error
        except ValueError as error:
            raise QAppClientError("qApp returned invalid JSON") from error

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

    # Replace article body text tool
    async def replace_article_body_text(
        self,
        *,
        access_token: str,
        article_id: str,
        old_text: str,
        new_text: str,
    ) -> Any:
        """Replace one exact piece of text in an article draft body through qApp."""
        return await self.patch_json(
            f"/articles/api/v1/articles/{article_id}/body-text",
            payload={
                "old_text": old_text,
                "new_text": new_text,
            },
            access_token=access_token,
        )

    async def post_file(
        self,
        path: str,
        *,
        file_name: str,
        file_bytes: bytes,
        form_data: Mapping[str, str] | None = None,
        access_token: str | None = None,
    ) -> Any:
        """POST multipart/form-data with a single file field to qApp."""
        if self._client is None:
            raise QAppClientError(
                "QAppClient must be used as an async context manager"
            )

        headers = (
            {"Authorization": f"Bearer {access_token}"}
            if access_token
            else None
        )

        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type:
            mime_type = "application/octet-stream"

        files = {"file": (file_name, file_bytes, mime_type)}

        try:
            response = await self._client.post(
                path,
                files=files,
                data=dict(form_data) if form_data else None,
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

    async def upload_article_file(
        self,
        *,
        access_token: str,
        article_id: str,
        file_name: str,
        file_bytes: bytes,
        convert_to_webp: bool = True,
    ) -> Any:
        """Upload a file to a Quollnet article's file folder."""
        return await self.post_file(
            f"/articles/api/v1/articles/{article_id}/files",
            file_name=file_name,
            file_bytes=file_bytes,
            form_data={"convert-to-webp": "yes" if convert_to_webp else "no"},
            access_token=access_token,
        )

    async def list_article_files(
        self,
        *,
        access_token: str,
        article_id: str,
    ) -> Any:
        """List files stored for a Quollnet article."""
        return await self.get_json(
            f"/articles/api/v1/articles/{article_id}/files",
            access_token=access_token,
        )

    async def rename_article_file(
        self,
        *,
        access_token: str,
        article_id: str,
        file_name: str,
        new_name: str,
    ) -> Any:
        """Rename an existing file in a Quollnet article folder."""
        safe_name = urllib.parse.quote(file_name, safe="")
        return await self.patch_json(
            f"/articles/api/v1/articles/{article_id}/files/{safe_name}",
            payload={"new_name": new_name},
            access_token=access_token,
        )

    async def set_article_hero_image(
        self,
        *,
        access_token: str,
        article_id: str,
        file_name: str,
    ) -> Any:
        """Assign an existing article file as the article hero image."""
        return await self.patch_json(
            f"/articles/api/v1/articles/{article_id}/hero",
            payload={"file_name": file_name},
            access_token=access_token,
        )

    # ------------------------------------------------------------------
    # Quollnet qTools V2
    # ------------------------------------------------------------------

    async def get_qtool_generation_spec(
        self,
        *,
        access_token: str,
    ) -> Any:
        return await self.get_json(
            "/tools/api/v2/generation-spec",
            access_token=access_token,
        )

    async def list_qtools(
        self,
        *,
        access_token: str,
        page: int = 1,
        per_page: int = 25,
        status: str | None = None,
    ) -> Any:
        params = {
            "page": page,
            "per_page": per_page,
        }
        if status is not None:
            params["status"] = status

        return await self.get_json(
            "/tools/api/v2/",
            params=params,
            access_token=access_token,
        )

    async def get_qtool(
        self,
        *,
        access_token: str,
        slug: str,
    ) -> Any:
        return await self.get_json(
            f"/tools/api/v2/{slug}",
            access_token=access_token,
        )

    async def create_qtool(
        self,
        *,
        access_token: str,
        payload: Mapping[str, Any],
    ) -> Any:
        return await self.post_json(
            "/tools/api/v2/",
            payload=payload,
            access_token=access_token,
        )

    async def update_qtool_metadata(
        self,
        *,
        access_token: str,
        slug: str,
        payload: Mapping[str, Any],
    ) -> Any:
        return await self.patch_json(
            f"/tools/api/v2/{slug}",
            payload=payload,
            access_token=access_token,
        )

    async def list_qtool_files(
        self,
        *,
        access_token: str,
        slug: str,
    ) -> Any:
        return await self.get_json(
            f"/tools/api/v2/{slug}/files",
            access_token=access_token,
        )

    async def get_qtool_file(
        self,
        *,
        access_token: str,
        slug: str,
        relative_path: str,
    ) -> Any:
        safe_path = urllib.parse.quote(relative_path, safe="/")
        return await self.get_json(
            f"/tools/api/v2/{slug}/files/{safe_path}",
            access_token=access_token,
        )

    async def write_qtool_file(
        self,
        *,
        access_token: str,
        slug: str,
        relative_path: str,
        payload: Mapping[str, Any],
    ) -> Any:
        safe_path = urllib.parse.quote(relative_path, safe="/")
        return await self.put_json(
            f"/tools/api/v2/{slug}/files/{safe_path}",
            payload=payload,
            access_token=access_token,
        )

    async def delete_qtool_file(
        self,
        *,
        access_token: str,
        slug: str,
        relative_path: str,
    ) -> Any:
        safe_path = urllib.parse.quote(relative_path, safe="/")
        return await self.delete_json(
            f"/tools/api/v2/{slug}/files/{safe_path}",
            access_token=access_token,
        )

    async def save_qtool(
        self,
        *,
        access_token: str,
        slug: str,
    ) -> Any:
        return await self.post_json(
            f"/tools/api/v2/{slug}/save",
            payload={},
            access_token=access_token,
        )

    async def publish_qtool(
        self,
        *,
        access_token: str,
        slug: str,
        version: int | None = None,
    ) -> Any:
        payload = {}
        if version is not None:
            payload["version"] = version
        return await self.post_json(
            f"/tools/api/v2/{slug}/publish",
            payload=payload,
            access_token=access_token,
        )

    async def disable_qtool(
        self,
        *,
        access_token: str,
        slug: str,
    ) -> Any:
        return await self.post_json(
            f"/tools/api/v2/{slug}/disable",
            payload={},
            access_token=access_token,
        )

    async def set_qtool_indexing(
        self,
        *,
        access_token: str,
        slug: str,
        indexed: bool,
    ) -> Any:
        return await self.patch_json(
            f"/tools/api/v2/{slug}/indexing",
            payload={"indexed": indexed},
            access_token=access_token,
        )
