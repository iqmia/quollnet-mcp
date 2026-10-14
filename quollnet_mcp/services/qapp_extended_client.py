from collections.abc import Mapping
from typing import Any

import httpx

from quollnet_mcp.services.qapp_client import QAppClient, QAppClientError


class QAppExtendedClient(QAppClient):
    """QAppClient with the JSON DELETE transport needed by lifecycle tools."""

    async def delete_json(
        self,
        path: str,
        payload: Mapping[str, Any],
        access_token: str | None = None,
    ) -> Any:
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
            response = await self._client.request(
                "DELETE",
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
