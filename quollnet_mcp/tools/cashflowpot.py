from typing import Annotated, Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from quollnet_mcp.dependencies import qauth_client, qflow_client
from quollnet_mcp.services.qauth_client import QAuthClientError
from quollnet_mcp.services.qflow_client import QFlowClientError


class CashflowActivityInput(BaseModel):
    """One activity in the portable CashflowPot input model."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=64)]
    activity_type: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description=(
                "Activity category/type. Known q_flow presets may supply a default "
                "skew; other descriptive values remain valid."
            ),
        ),
    ] = "General"
    cost: Annotated[float, Field(gt=0)]
    duration: Annotated[int, Field(gt=0)]
    duration_units: Annotated[str, Field(min_length=1, max_length=64)] = "Months"
    start: Annotated[int, Field(ge=0)] = 0
    advance: Annotated[float, Field(ge=0, le=1)] = 0.10
    retention: Annotated[float, Field(ge=0, le=1)] = 0.10
    release_retention_eop: Annotated[float, Field(ge=0, le=1)] = 0.50
    dlp: Annotated[int, Field(ge=0)] = 0
    duration_for_payment: Annotated[int, Field(ge=0)] = 1
    work_in_excess: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description=(
                "Activity billing deferral fraction. 0.10 means 10% of completed "
                "work is carried into the following billing period."
            ),
        ),
    ] = 0.10
    mobilization_period: Annotated[int, Field(ge=0)] = 1
    subcontracted: Annotated[float, Field(ge=0, le=1)] = 0.70
    skew: Annotated[
        float | None,
        Field(
            gt=-1,
            lt=1,
            description=(
                "Optional activity cost-distribution skew. Omit to let q_flow "
                "derive the normal preset from activity_type."
            ),
        ),
    ] = None
    no_billing_period: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def validate_advance_and_retention(self) -> "CashflowActivityInput":
        if self.advance + self.retention > 1:
            raise ValueError("activity advance + retention must not exceed 1")
        return self


class CashflowInput(BaseModel):
    """Portable CashflowPot scenario input. q_flow remains authoritative."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=64)]
    description: Annotated[str, Field(max_length=256)] = ""
    contract_value: Annotated[float, Field(ge=0)] = 0
    advance: Annotated[float, Field(ge=0, le=1)] = 0.10
    retention: Annotated[float, Field(ge=0, le=1)] = 0.10
    release_retention_eop: Annotated[float, Field(ge=0, le=1)] = 0.50
    dlp: Annotated[int, Field(ge=0)] = 12
    duration_for_payment: Annotated[int, Field(ge=0)] = 1
    interest_rate: Annotated[float, Field(ge=0)] = 0.005
    wieb: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            description=(
                "Project billing deferral fraction. 0.20 means 20% of completed "
                "work is carried into the following billing period."
            ),
        ),
    ] = 0.20
    activities: list[CashflowActivityInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_advance_and_retention(self) -> "CashflowInput":
        if self.advance + self.retention > 1:
            raise ValueError("cashflow advance + retention must not exceed 1")
        return self


async def _cashflowpot_user_token() -> str:
    access_token = get_access_token()
    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    try:
        return await qauth_client.exchange_app_token(
            mcp_access_token=access_token.token,
            target_app_id=qauth_client.settings.cashflowpot_app_id,
        )
    except QAuthClientError as error:
        raise ToolError(str(error)) from error


async def list_cashflow_projects(
    page: Annotated[int, Field(ge=1)] = 1,
    per_page: Annotated[int, Field(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    """List CashflowPot projects available to the authenticated Quollnet user.

    Projects are QAuth Units. The response also includes compact existing cashflow
    scenarios for each project. Use the returned project id as unit_id when
    creating a scenario.
    """
    app_token = await _cashflowpot_user_token()
    try:
        return await qflow_client.list_projects(
            access_token=app_token,
            page=page,
            per_page=per_page,
        )
    except QFlowClientError as error:
        raise ToolError(str(error)) from error


async def create_cashflow(
    unit_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            description="CashflowPot project/QAuth Unit ID from list_cashflow_projects.",
        ),
    ],
    cashflow: CashflowInput,
) -> dict[str, Any]:
    """Create a calculated CashflowPot scenario in an existing project.

    Supply commercial assumptions and activities only. Percentages are fractions
    (0.10 = 10%) and timing values are integer model periods. Do not calculate
    workflow, inflow, outflow, netflow, financing balances, IDs, or ownership;
    q_flow validates the input, calculates the scenario, and returns the
    authoritative result.
    """
    app_token = await _cashflowpot_user_token()
    payload = {
        "format": "cashflowpot.cashflow",
        "version": 1,
        "cashflow": cashflow.model_dump(exclude_none=True),
    }
    try:
        return await qflow_client.import_cashflow(
            access_token=app_token,
            unit_id=unit_id,
            payload=payload,
        )
    except QFlowClientError as error:
        raise ToolError(str(error)) from error
