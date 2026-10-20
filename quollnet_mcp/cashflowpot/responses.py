"""Public CashflowPot response contracts and recursive allowlist projection.

Backend responses can contain refreshed bearer tokens and ORM metadata.  Only
fields declared here are returned by the dedicated MCP tools.  The projection
preserves supplied financial values; it never calculates or fills defaults.
"""

from functools import lru_cache
from typing import Annotated, Literal, TypeVar

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import AfterValidator, ConfigDict, Field, StringConstraints, TypeAdapter, ValidationError, with_config
from typing_extensions import TypedDict

from quollnet_mcp.cashflowpot.models import _validate_schedule_period


_OUTPUT_CONFIG = ConfigDict(
    extra="ignore",
    allow_inf_nan=False,
    json_schema_extra={"additionalProperties": False},
)

Number = int | float
# q_flow accepts legacy int-parsable keys and preserves their spellings. The
# output boundary must not reject an already committed, backend-valid schedule.
PeriodKey = Annotated[
    str,
    StringConstraints(pattern=r"^\s*[+-]?\d(?:_?\d)*\s*$"),
    AfterValidator(_validate_schedule_period),
]
PeriodSchedule = Annotated[
    dict[PeriodKey, Number],
    Field(json_schema_extra={"additionalProperties": False}),
]


@with_config(_OUTPUT_CONFIG)
class ActivitySource(TypedDict, total=False):
    name: str | None
    activity_type: str | None
    activity_mode: str | None
    distribution_type: str | None
    cost_schedule_json: list[Number] | None
    cost: Number | None
    duration: int | None
    duration_units: str | None
    start: int | None
    advance: Number | None
    retention: Number | None
    release_retention_eop: Number | None
    dlp: int | None
    duration_for_payment: int | None
    work_in_excess: Number | None
    mobilization_period: int | None
    subcontracted: Number | None
    skew: Number | None
    no_billing_period: int | None


@with_config(_OUTPUT_CONFIG)
class Activity(ActivitySource, total=False):
    id: str
    cashflow_id: str
    is_deleted: bool | None


@with_config(_OUTPUT_CONFIG)
class Facility(TypedDict, total=False):
    id: str | None
    name: str
    type: str
    draw_method: str
    repayment_method: str
    start: int | None
    end: int | None
    limit: Number | None
    revolving: bool
    interest_rate: Number | None
    fees: Number | None
    sweep_priority: int | None
    draw_schedule: PeriodSchedule
    repayment_schedule: PeriodSchedule
    advance_portion: Number | None
    repayment_percent: Number | None
    installment_start: int | None
    installment_interval: int | None
    installment_count: int | None


@with_config(_OUTPUT_CONFIG)
class ContractProperties(TypedDict, total=False):
    contract_value: Number | None
    advance: Number | None
    retention: Number | None
    release_retention_eop: Number | None
    dlp: int | None
    duration_for_payment: int | None


@with_config(_OUTPUT_CONFIG)
class ForecastProperties(TypedDict, total=False):
    wieb: Number | None
    interest_rate: Number | None
    use_independent_inflow_curve: bool | None
    inflow_curve_type: str | None
    inflow_curve_skew: Number | None


@with_config(_OUTPUT_CONFIG)
class UnitsMetadata(TypedDict, total=False):
    period_index_base: Literal[0]
    percentages: Literal["fraction"]
    interest_rate_basis: Literal["per_model_period"]
    amount_unit: Literal["project_currency"]
    period_unit: Literal["model_period"]


@with_config(_OUTPUT_CONFIG)
class CashflowProperties(TypedDict, total=False):
    contract: ContractProperties
    forecast: ForecastProperties
    activities: list[Activity]
    financing: list[Facility]
    units: UnitsMetadata


@with_config(_OUTPUT_CONFIG)
class CashflowSourceProperties(ContractProperties, ForecastProperties, total=False):
    name: str | None
    description: str | None
    financing_facilities: list[Facility] | None


@with_config(_OUTPUT_CONFIG)
class Summary(TypedDict, total=False):
    total_inflow: Number
    work_cost: Number
    scheduled_cost: Number
    subcontracted_cost: Number
    self_performed_cost: Number
    direct_cost: Number
    financing_cost: Number
    total_cost: Number
    total_facility_interest: Number
    total_facility_fees: Number
    minimum_pre_financing_balance: Number
    minimum_pre_financing_period: int | None
    peak_pre_financing_need: Number
    peak_pre_financing_period: int | None
    peak_facility_outstanding: Number
    final_facility_outstanding: Number
    final_cash_balance: Number
    cash_after_debt_settlement: Number
    work_duration: int
    dlp: int
    financial_horizon: int
    contractor_contribution: Number
    peak_unfunded_shortfall: Number


@with_config(_OUTPUT_CONFIG)
class FacilityRow(TypedDict, total=False):
    id: str | None
    name: str
    type: str
    draw_method: str
    repayment_method: str
    draw: list[Number]
    repayment: list[Number]
    interest: list[Number]
    fees: list[Number]
    outstanding: list[Number]
    available_limit: list[Number | None]


@with_config(_OUTPUT_CONFIG)
class ResultsResponse(TypedDict, total=False):
    id: str
    unit_id: str | None
    name: str | None
    summary: Summary
    workflow: Annotated[list[Number], Field(description="Work activity cost distributed over zero-based periods; Scheduled Cost activities do not contribute physical work.")]
    inflow: Annotated[list[Number], Field(description="Employer receipts per period before financing facility draws, in project currency.")]
    outflow: Annotated[list[Number], Field(description="Activity payments per period before financing costs and repayments, in project currency.")]
    netflow: Annotated[list[Number], Field(description="Period employer inflow minus activity outflow before financing.")]
    pre_financing_balance: Annotated[list[Number], Field(description="Cumulative employer inflow minus activity outflow before financing; present when explicit facilities are modeled.")]
    facility_rows: list[FacilityRow]
    facility_inflow: list[Number]
    facility_outflow: list[Number]
    facility_interest: list[Number]
    facility_fees: list[Number]
    funded_netflow: Annotated[list[Number], Field(description="Net period cash movement including facility draws, principal repayments, interest and fees.")]
    unfunded_shortfall: Annotated[list[Number], Field(description="Positive remaining funding shortfall per period after the modeled facilities.")]
    outflow_with_interest: Annotated[list[Number], Field(description="Legacy field name for the cumulative cash balance after financing: funded balance when facilities are present, otherwise balance with legacy scenario interest. This is a balance, not period outflow.")]
    properties: Annotated[CashflowProperties, Field(description="Current backend-supplied properties used to calculate this scenario. No source/provenance is inferred, and unavailable legacy values are not invented.")]


@with_config(_OUTPUT_CONFIG)
class CashflowSnapshot(CashflowSourceProperties, ResultsResponse, total=False):
    activities: list[Activity]
    duration: int


@with_config(_OUTPUT_CONFIG)
class ProjectScenario(TypedDict, total=False):
    id: str
    unit_id: str | None
    name: str | None
    description: str | None


@with_config(_OUTPUT_CONFIG)
class Project(TypedDict, total=False):
    id: str | None
    name: str
    description: str
    cashflows: list[ProjectScenario]


@with_config(_OUTPUT_CONFIG)
class ProjectResponse(TypedDict, total=False):
    data: Project
    message: str


@with_config(_OUTPUT_CONFIG)
class ProjectListResponse(TypedDict, total=False):
    data: list[Project]
    pages: int


@with_config(_OUTPUT_CONFIG)
class CashflowResponse(TypedDict, total=False):
    data: CashflowSnapshot
    message: str


@with_config(_OUTPUT_CONFIG)
class ActivityResponse(TypedDict, total=False):
    data: Activity
    cashflow: CashflowSnapshot
    cashflows: list[CashflowSnapshot]
    message: str


@with_config(_OUTPUT_CONFIG)
class ActivityListResponse(TypedDict, total=False):
    data: list[Activity]
    message: str


@with_config(_OUTPUT_CONFIG)
class FacilityListResponse(TypedDict, total=False):
    data: list[Facility]
    message: str


@with_config(_OUTPUT_CONFIG)
class FacilityResponse(TypedDict, total=False):
    data: Facility
    facility: Facility
    cashflow: CashflowSnapshot
    message: str


@with_config(_OUTPUT_CONFIG)
class MessageResponse(TypedDict, total=False):
    message: str


@with_config(_OUTPUT_CONFIG)
class ExcelResponse(TypedDict, total=False):
    filename: str
    download_url: str
    expires_at: str
    message: str


@with_config(_OUTPUT_CONFIG)
class ActivityTypePreset(TypedDict, total=False):
    type: str
    name: str
    description: str
    distribution_type: str
    advance: Number
    subcontracted: Number
    retention: Number
    release_retention_eop: Number
    dlp: int
    duration_for_payment: int
    work_in_excess: Number
    no_billing_period: int
    skew: Number
    mobilization_period: int


@with_config(_OUTPUT_CONFIG)
class ActivityTypesResponse(TypedDict, total=False):
    data: dict[str, ActivityTypePreset]


@with_config(_OUTPUT_CONFIG)
class FacilityPreset(TypedDict, total=False):
    key: str
    type: str
    draw_method: str
    repayment_method: str
    revolving: bool
    interest_rate: Number
    fees: Number
    interest_rate_basis: Literal["per_period"]
    fees_basis: Literal["fixed_amount"]
    default_fees_rate: Number
    default_fees_basis: Literal["limit_or_scheduled_draw_total"]
    costs_note: str


@with_config(_OUTPUT_CONFIG)
class FacilityPresetsResponse(TypedDict, total=False):
    data: list[FacilityPreset]


@with_config(_OUTPUT_CONFIG)
class PortableCashflow(CashflowSourceProperties, total=False):
    activities: list[ActivitySource]


@with_config(_OUTPUT_CONFIG)
class PortableResponse(TypedDict, total=False):
    format: Literal["cashflowpot.cashflow"]
    version: Literal[1]
    cashflow: PortableCashflow


ResponseT = TypeVar("ResponseT")

_SUCCESS_MESSAGES = frozenset({
    "Project created successfully",
    "Project updated successfully",
    "Project deleted successfully",
    "Project restored successfully",
    "Project hard deleted successfully",
    "Cashflow created successfully",
    "Cashflow imported successfully",
    "Cashflow updated successfully",
    "Cashflow deleted successfully",
    "Cashflow restored successfully",
    "Cashflow hard deleted successfully",
    "Activity created successfully",
    "Activity retrieved successfully",
    "Activity updated successfully",
    "Activity deleted successfully",
    "Activity restored successfully",
    "Activity hard deleted successfully",
    "Activities restored successfully",
    "Financing facility created successfully",
    "Financing facility updated successfully",
    "Financing facility deleted successfully",
    "Financing facility order updated successfully",
    "Excel export link created. The workbook is generated on download and is not stored on the MCP server.",
})


@lru_cache(maxsize=None)
def _response_adapter(response_type: type[ResponseT]) -> TypeAdapter[ResponseT]:
    return TypeAdapter(response_type)


def project_response(value: object, response_type: type[ResponseT]) -> ResponseT:
    """Validate and recursively project a backend response onto its public schema.

    Do not include validation details or the rejected response in errors: either
    can contain refreshed credentials or other private backend data.
    """
    if isinstance(value, dict) and "message" in value:
        value = dict(value)
        message = value["message"]
        if not isinstance(message, str) or message not in _SUCCESS_MESSAGES:
            value["message"] = "CashflowPot request completed."
    try:
        return _response_adapter(response_type).validate_python(value, strict=True)
    except (ValidationError, TypeError, ValueError) as error:
        raise ToolError("CashflowPot returned an invalid response") from error
