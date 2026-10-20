import urllib.parse
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Any

import httpx

from quollnet_mcp.config import Settings, get_settings
from quollnet_mcp.cashflowpot.token_store import accept_cashflowpot_token_from_qflow


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

    @staticmethod
    def _quote(value: str) -> str:
        return urllib.parse.quote(value, safe="")

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
            data = response.json()

            # q_flow handles Unit loading and expired-token refresh. It may
            # return a replacement bearer in the Authorization header and/or
            # at the root of its JSON response. Adopt it for future MCP calls.
            replacement = response.headers.get("Authorization")
            if isinstance(data, dict):
                replacement = replacement or data.get("token")
                # Never expose an internal QAuth bearer to ChatGPT.
                data.pop("token", None)
            accept_cashflowpot_token_from_qflow(
                sent_token=access_token,
                replacement_token=replacement,
            )
            return data
        except httpx.HTTPStatusError as error:
            # Upstream messages can contain SQL errors, credentials or user
            # identifiers. Do not copy arbitrary response bodies into tool errors.
            status = error.response.status_code
            details = {
                400: "Invalid CashflowPot input; check the supplied properties and schedules.",
                401: "Authentication expired or is invalid; reconnect CashflowPot.",
                403: "Access denied for this project or operation.",
                404: "The requested CashflowPot item was not found or is unavailable.",
                409: "The requested change conflicts with the current item state.",
                422: "Invalid CashflowPot input; check the supplied properties and schedules.",
                429: "CashflowPot is temporarily rate limited; retry later.",
            }
            message = details.get(status, "CashflowPot could not complete the request; retry later.")
            raise QFlowClientError(f"CashflowPot returned HTTP {status}: {message}") from error
        except httpx.RequestError as error:
            raise QFlowClientError("q_flow request failed") from error
        except ValueError as error:
            raise QFlowClientError("q_flow returned invalid JSON") from error

    # Projects
    async def list_projects(self, *, access_token: str, page: int = 1, per_page: int = 25) -> Any:
        return await self._request_json(
            "GET", "/projects", access_token=access_token,
            params={"page": page, "per_page": per_page},
        )

    async def get_project(self, *, access_token: str, unit_id: str) -> Any:
        return await self._request_json(
            "GET", f"/project/{self._quote(unit_id)}", access_token=access_token
        )

    async def create_project(self, *, access_token: str, payload: Mapping[str, Any]) -> Any:
        return await self._request_json(
            "POST", "/new_project", access_token=access_token, payload=payload
        )

    async def update_project(self, *, access_token: str, unit_id: str, payload: Mapping[str, Any]) -> Any:
        return await self._request_json(
            "PUT", f"/update_project/{self._quote(unit_id)}",
            access_token=access_token, payload=payload,
        )

    async def delete_project(self, *, access_token: str, unit_id: str) -> Any:
        return await self._request_json(
            "DELETE", f"/delete_project/{self._quote(unit_id)}", access_token=access_token
        )

    async def restore_project(self, *, access_token: str, unit_id: str) -> Any:
        return await self._request_json(
            "PUT", f"/restore_project/{self._quote(unit_id)}", access_token=access_token
        )

    async def hard_delete_project(self, *, access_token: str, unit_id: str) -> Any:
        return await self._request_json(
            "DELETE", f"/hard_delete_project/{self._quote(unit_id)}", access_token=access_token
        )

    # Cashflows
    async def get_cashflow(self, *, access_token: str, cashflow_id: str, detail: str | None = None) -> Any:
        return await self._request_json(
            "GET", f"/cashflow/{self._quote(cashflow_id)}", access_token=access_token,
            params={"detail": detail} if detail is not None else None,
        )

    async def create_cashflow(self, *, access_token: str, unit_id: str, payload: Mapping[str, Any]) -> Any:
        return await self._request_json(
            "POST", f"/project/{self._quote(unit_id)}/cashflows",
            access_token=access_token, payload=payload,
        )

    async def update_cashflow(self, *, access_token: str, cashflow_id: str, payload: Mapping[str, Any]) -> Any:
        return await self._request_json(
            "PUT", f"/cashflow/{self._quote(cashflow_id)}",
            access_token=access_token, payload=payload,
        )

    async def delete_cashflow(self, *, access_token: str, cashflow_id: str) -> Any:
        return await self._request_json(
            "DELETE", f"/cashflow/{self._quote(cashflow_id)}", access_token=access_token
        )

    async def restore_cashflow(self, *, access_token: str, cashflow_id: str) -> Any:
        return await self._request_json(
            "PUT", f"/cashflow/{self._quote(cashflow_id)}/restore", access_token=access_token
        )

    async def hard_delete_cashflow(self, *, access_token: str, cashflow_id: str) -> Any:
        return await self._request_json(
            "DELETE", f"/cashflow/{self._quote(cashflow_id)}/hard", access_token=access_token
        )

    async def import_cashflow(
        self, *, access_token: str, unit_id: str, payload: Mapping[str, Any]
    ) -> Any:
        return await self._request_json(
            "POST", f"/project/{self._quote(unit_id)}/cashflows/import",
            access_token=access_token, payload=payload,
        )

    async def export_cashflow(self, *, access_token: str, cashflow_id: str) -> Any:
        return await self._request_json(
            "GET", f"/cashflow/{self._quote(cashflow_id)}/export", access_token=access_token
        )

    # Activities
    async def get_activity_types(self, *, access_token: str) -> Any:
        return await self._request_json("GET", "/activities/types", access_token=access_token)

    async def get_activity(self, *, access_token: str, activity_id: str) -> Any:
        return await self._request_json(
            "GET", f"/activity/{self._quote(activity_id)}", access_token=access_token
        )

    async def create_activity(self, *, access_token: str, cashflow_id: str, payload: Mapping[str, Any]) -> Any:
        return await self._request_json(
            "POST", f"/new_activity/{self._quote(cashflow_id)}",
            access_token=access_token, payload=payload,
        )

    async def update_activity(self, *, access_token: str, activity_id: str, payload: Mapping[str, Any]) -> Any:
        return await self._request_json(
            "PUT", f"/update_activity/{self._quote(activity_id)}",
            access_token=access_token, payload=payload,
        )

    async def delete_activity(self, *, access_token: str, activity_id: str) -> Any:
        return await self._request_json(
            "DELETE", f"/delete_activity/{self._quote(activity_id)}", access_token=access_token
        )

    async def restore_activity(self, *, access_token: str, activity_id: str) -> Any:
        return await self._request_json(
            "PUT", f"/restore_activity/{self._quote(activity_id)}", access_token=access_token
        )

    async def restore_activities(self, *, access_token: str, activity_ids: Sequence[str]) -> Any:
        return await self._request_json(
            "PUT", "/restore_activities", access_token=access_token,
            payload={"data": list(activity_ids)},
        )

    async def hard_delete_activity(self, *, access_token: str, activity_id: str) -> Any:
        return await self._request_json(
            "DELETE", f"/hard_delete_activity/{self._quote(activity_id)}", access_token=access_token
        )

    async def list_deleted_activities(self, *, access_token: str, cashflow_id: str) -> Any:
        return await self._request_json(
            "GET", f"/deleted_activities/{self._quote(cashflow_id)}", access_token=access_token
        )

    # Financing facilities
    async def list_financing_facility_presets(self, *, access_token: str) -> Any:
        return await self._request_json(
            "GET", "/financing-facility-presets", access_token=access_token
        )

    async def list_financing_facilities(self, *, access_token: str, cashflow_id: str) -> Any:
        return await self._request_json(
            "GET", f"/cashflow/{self._quote(cashflow_id)}/facilities", access_token=access_token
        )

    async def get_financing_facility(self, *, access_token: str, cashflow_id: str, facility_id: str) -> Any:
        return await self._request_json(
            "GET",
            f"/cashflow/{self._quote(cashflow_id)}/facilities/{self._quote(facility_id)}",
            access_token=access_token,
        )

    async def add_financing_facility(self, *, access_token: str, cashflow_id: str, payload: Mapping[str, Any]) -> Any:
        return await self._request_json(
            "POST", f"/cashflow/{self._quote(cashflow_id)}/facilities",
            access_token=access_token, payload=payload,
        )

    async def update_financing_facility(
        self, *, access_token: str, cashflow_id: str, facility_id: str,
        payload: Mapping[str, Any],
    ) -> Any:
        return await self._request_json(
            "PUT",
            f"/cashflow/{self._quote(cashflow_id)}/facilities/{self._quote(facility_id)}",
            access_token=access_token, payload=payload,
        )

    async def delete_financing_facility(self, *, access_token: str, cashflow_id: str, facility_id: str) -> Any:
        return await self._request_json(
            "DELETE",
            f"/cashflow/{self._quote(cashflow_id)}/facilities/{self._quote(facility_id)}",
            access_token=access_token,
        )

    async def set_financing_facility_order(
        self, *, access_token: str, cashflow_id: str, facility_ids: Sequence[str]
    ) -> Any:
        return await self._request_json(
            "PUT", f"/cashflow/{self._quote(cashflow_id)}/facilities/order",
            access_token=access_token, payload={"facility_ids": list(facility_ids)},
        )

    # Exports
    async def request_excel_export(self, *, access_token: str, cashflow_id: str) -> Any:
        return await self._request_json(
            "POST", f"/cashflow/{self._quote(cashflow_id)}/excel-export",
            access_token=access_token,
        )
