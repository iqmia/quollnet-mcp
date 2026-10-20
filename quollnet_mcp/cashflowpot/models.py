"""Discoverable source schemas for the authoritative q_flow calculations.

Money is expressed in the scenario currency, percentages are fractions, and
integer timing values use model periods rather than assuming calendar months.
Cross-field rules that depend on existing state remain with the backend.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool, model_validator


FiniteNumber = Annotated[float, Field(allow_inf_nan=False, strict=True)]
NonNegativeNumber = Annotated[FiniteNumber, Field(ge=0)]
PositiveNumber = Annotated[FiniteNumber, Field(gt=0)]
Fraction = Annotated[FiniteNumber, Field(ge=0, le=1)]
CurveSkew = Annotated[FiniteNumber, Field(gt=-1, lt=1)]
NonNegativePeriod = Annotated[int, Field(ge=0, strict=True)]
PositivePeriod = Annotated[int, Field(ge=1, strict=True)]
ActivityMode = Literal["work", "scheduled_cost"]
DistributionType = Literal["s_curve", "linear", "manual"]
InflowCurveType = Literal["s_curve", "linear"]
DrawMethod = Literal["automatic_shortfall", "scheduled", "ppc_base"]
RepaymentMethod = Literal[
    "cashflow_sweep", "percent_of_ppc", "equal_installments", "scheduled"
]


def _validate_schedule_period(value: str) -> str:
    """Match q_flow's integer parsing without narrowing accepted key spellings."""
    try:
        period = int(value)
    except (TypeError, ValueError):
        raise ValueError("schedule period must be a non-negative integer") from None
    if period < 0:
        raise ValueError("schedule period must be a non-negative integer")
    return value


SchedulePeriod = Annotated[str, AfterValidator(_validate_schedule_period)]
FacilitySchedule = dict[SchedulePeriod, NonNegativeNumber]

_ACTIVITY_DEFAULT = (
    " Omit/null on creation for the backend default; omit on update to keep the "
    "current value, or send null for backend defaulting/validation."
)
_CASHFLOW_DEFAULT = (
    " Omit/null on creation for the backend default; omit on update to keep the "
    "current value. Explicit update null is forwarded for backend validation."
)
_FACILITY_DEFAULT = (
    " Omit on creation to let the backend resolve its preset; "
    "omit on update to keep the current value. Explicit null on update is "
    "forwarded for field-specific backend validation, not a general reset."
)


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1, max_length=128,
        description="Project display name; required non-empty text, up to 128 characters.",
    )
    description: str = Field(
        default="", max_length=1000,
        description="Project description in plain text; omitted means an empty description.",
    )
    color: str | None = Field(
        default=None,
        description="Project display color understood by QAuth; omit/null to use its default color.",
    )
    contract_value: PositiveNumber | None = Field(
        default=None,
        description="Optional initial Base Cashflow contract value in currency units, greater than zero; omit/null to use the backend's initial contract value.",
    )


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None, min_length=1, max_length=128,
        description="Replacement project display name, up to 128 characters; omit to retain it. Explicit null is validated by QAuth.",
    )
    description: str | None = Field(
        default=None, max_length=1000,
        description="Replacement project description; omit to retain it, use empty text to clear it. Explicit null is validated by QAuth.",
    )
    color: str | None = Field(
        default=None,
        description="Replacement project display color; omit to retain it. Explicit null is forwarded to QAuth for reset/validation.",
    )


class ActivityUpdate(BaseModel):
    """Partial source update; q_flow merges it before validating the activity."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None, min_length=1, max_length=64,
        description="Activity display name; omit on update to retain it. Explicit null is forwarded for backend validation.",
    )
    activity_type: str | None = Field(
        default=None,
        description="Backend activity category/template code, obtained from get_activity_types; free text for legacy/custom categories. Legacy 'linear' implies linear distribution when distribution_type is absent." + _ACTIVITY_DEFAULT,
    )
    activity_mode: ActivityMode | None = Field(
        default=None,
        description="work generates physical progress and subcontract payments; scheduled_cost posts direct scheduled outflows without physical work or client billing. The legacy default is work." + _ACTIVITY_DEFAULT,
    )
    distribution_type: DistributionType | None = Field(
        default=None,
        description="Work cost distribution: s_curve, linear, or manual. scheduled_cost uses manual. Null/omitted legacy values infer linear from activity_type='linear', otherwise s_curve; updates use backend normalization.",
    )
    cost_schedule_json: list[NonNegativeNumber] | None = Field(
        default=None,
        description="Dense activity-local cost amounts in currency units, indexed from zero; start shifts them into project time. Manual Work and Scheduled Cost require a non-empty list with positive total; q_flow derives cost and duration. Omit/null for generated Work; update omission retains the schedule.",
    )
    cost: PositiveNumber | None = Field(
        default=None,
        description="Total estimated activity cost in currency units, greater than zero for generated Work. Manual Work/Scheduled Cost derive it from the schedule. Generated creation requires cost; update omission retains it and explicit null is backend-validated.",
    )
    duration: PositivePeriod | None = Field(
        default=None,
        description="Number of model periods of generated Work, greater than zero. Manual Work/Scheduled Cost derive it from schedule length. Generated creation requires duration; update omission retains it and explicit null is backend-validated.",
    )
    duration_units: str | None = Field(
        default=None,
        description="Free-text period-unit label such as Months, Weeks, or Periods; it labels duration without converting timing values." + _ACTIVITY_DEFAULT,
    )
    start: NonNegativePeriod | None = Field(
        default=None,
        description="Zero-based project period offset: start=0 is frontend P1, start=1 is frontend P2. Physical work starts after any mobilization_period delay." + _ACTIVITY_DEFAULT,
    )
    advance: Fraction | None = Field(
        default=None,
        description="Fraction of activity cost advanced to the subcontractor before work; 0.10 means 10%. advance + retention must not exceed one for Work." + _ACTIVITY_DEFAULT,
    )
    retention: Fraction | None = Field(
        default=None,
        description="Fraction withheld from subcontract invoices; 0.10 means 10%. advance + retention must not exceed one for Work." + _ACTIVITY_DEFAULT,
    )
    release_retention_eop: Fraction | None = Field(
        default=None,
        description="Fraction of subcontract retention released at the first/end-of-progress release point; the balance is released after dlp." + _ACTIVITY_DEFAULT,
    )
    dlp: NonNegativePeriod | None = Field(
        default=None,
        description="Defects liability delay in model periods between the first and final subcontract retention releases." + _ACTIVITY_DEFAULT,
    )
    duration_for_payment: NonNegativePeriod | None = Field(
        default=None,
        description="Subcontract invoice-to-payment delay in model periods; zero means payment without an additional period delay." + _ACTIVITY_DEFAULT,
    )
    work_in_excess: Fraction | None = Field(
        default=None,
        description="Fraction of completed subcontract Work carried into the next billing period; affects timing rather than total cost. Not used for Scheduled Cost." + _ACTIVITY_DEFAULT,
    )
    mobilization_period: NonNegativePeriod | None = Field(
        default=None,
        description="Initial number of no-work periods after activity start (legacy name; not a percentage). Defaults to 0 when omitted on creation; only use a positive value when the user requests a pre-work delay. Example: start=1 (frontend P2), duration=1, delay=0 means work and finish in P2; delay=1 means work and finish in P3. On update, omission retains the saved delay.",
    )
    subcontracted: Fraction | None = Field(
        default=None,
        description="Fraction of activity Work cost performed by subcontractors; 0 is entirely self-performed and 1 entirely subcontracted. Not used for Scheduled Cost." + _ACTIVITY_DEFAULT,
    )
    skew: CurveSkew | None = Field(
        default=None,
        description="Dimensionless generated S-curve skew strictly between -1 and 1; zero is balanced. On creation q_flow can select the activity category's skew; update omission retains the value and null uses its scalar default zero. Ignored for non-S-curve distributions.",
    )
    no_billing_period: NonNegativePeriod | None = Field(
        default=None,
        description="Initial subcontract billing window in model periods during which Work accumulates before the first invoice; not used for Scheduled Cost." + _ACTIVITY_DEFAULT,
    )

    @model_validator(mode="after")
    def validate_supplied_percentages(self) -> "ActivityUpdate":
        if self.advance is not None and self.retention is not None:
            if self.advance + self.retention > 1:
                raise ValueError("activity advance + retention must not exceed 1")
        return self


class ActivityInput(ActivityUpdate):
    """Activity source definition; q_flow owns normalization and calculation."""

    name: str = Field(
        min_length=1, max_length=64,
        description="Activity display name; required non-empty text, up to 64 characters.",
    )
    start: NonNegativePeriod = Field(
        default=0,
        description="Zero-based project period offset: start=0 is frontend P1, start=1 is frontend P2. Omitted start is 0. With duration=1 and no pre-work delay, start=1 means work finishes in P2.",
    )

    @model_validator(mode="after")
    def validate_source_shape(self) -> "ActivityInput":
        manual = self.distribution_type == "manual"
        scheduled = self.activity_mode == "scheduled_cost"
        if not (manual or scheduled) and (self.cost is None or self.duration is None):
            raise ValueError("generated Work requires cost and duration")
        return self


class FinancingFacilityUpdate(BaseModel):
    """Partial facility source update; q_flow validates the merged definition."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None, min_length=1, max_length=128,
        description="Facility display name, unique within the scenario; omit on update to retain it. Explicit null is backend-validated.",
    )
    type: str | None = Field(
        default=None,
        description="Editable facility product/category text, such as Overdraft or Equipment Loan. Discover current type presets with list_financing_facility_presets; custom types remain supported." + _FACILITY_DEFAULT,
    )
    draw_method: DrawMethod | None = Field(
        default=None,
        description="How principal is drawn: automatic_shortfall covers negative cash, scheduled uses draw_schedule, and ppc_base advances a fraction of issued client progress certificates." + _FACILITY_DEFAULT,
    )
    repayment_method: RepaymentMethod | None = Field(
        default=None,
        description="How principal is repaid: positive-cash cashflow_sweep, percent_of_ppc, equal_installments, or repayment_schedule when scheduled." + _FACILITY_DEFAULT,
    )
    start: NonNegativePeriod | None = Field(
        default=None,
        description="First zero-based project period eligible for draws; the one-off fee is charged in this period." + _FACILITY_DEFAULT,
    )
    end: NonNegativePeriod | None = Field(
        default=None,
        description="Last zero-based project period eligible for draws, inclusive; null means no end restriction. Omit on update to retain it; backend checks end is not before start.",
    )
    limit: NonNegativeNumber | None = Field(
        default=None,
        description="Facility capacity in currency units; null/omitted creation means unlimited, while zero allows no draws. Revolving limits apply to outstanding principal and other limits to cumulative draws; update omission retains it.",
    )
    revolving: StrictBool | None = Field(
        default=None,
        description="Whether repayment restores borrowing capacity under a finite limit; false caps cumulative draws instead." + _FACILITY_DEFAULT,
    )
    interest_rate: NonNegativeNumber | None = Field(
        default=None,
        description="Interest fraction per model period on opening outstanding principal; 0.01 means 1% per period, and explicit zero is interest-free. Draws accrue from the following period. Convert annual bank quotes only after confirming nominal/effective basis and periods/year: 7% nominal annual with monthly periods is 0.07/12, not 0.07." + _FACILITY_DEFAULT,
    )
    fees: NonNegativeNumber | None = Field(
        default=None,
        description="One-off financing fee in currency units charged at start; this is an amount, not a percentage. Explicit zero means no fee. Omitted new bank fees use facility value * 0.5% / 12, rounded to two decimals: value is the limit or, when unlimited, the scheduled draw total. Unknown value falls back to zero; enter a fee for unlimited facilities without a known value." + _FACILITY_DEFAULT,
    )
    sweep_priority: NonNegativePeriod | None = Field(
        default=None,
        description="Non-negative repayment priority for cashflow_sweep; lower numbers sweep first. Null leaves ordering to q_flow's default priority/rate behavior; update omission retains it.",
    )
    draw_schedule: FacilitySchedule | None = Field(
        default=None,
        description="For scheduled draws, mapping of zero-based project-period integer strings to finite non-negative currency amounts; absent periods draw zero. Omit on update to retain it, or use {} to clear it; explicit null is backend-validated and normally rejected.",
    )
    repayment_schedule: FacilitySchedule | None = Field(
        default=None,
        description="For scheduled repayments, mapping of zero-based project-period integer strings to finite non-negative currency amounts; absent periods repay zero. Omit on update to retain it, or use {} to clear it; explicit null is backend-validated and normally rejected.",
    )
    advance_portion: Fraction | None = Field(
        default=None,
        description="Fraction of issued client progress-certificate value requested as a ppc_base draw; 0.80 means 80%. Required by q_flow for ppc_base after preset/default resolution." + _FACILITY_DEFAULT,
    )
    repayment_percent: Fraction | None = Field(
        default=None,
        description="Fraction of the client progress-certificate repayment base applied to principal for percent_of_ppc; 0.25 means 25%. Required by q_flow for that method after default resolution." + _FACILITY_DEFAULT,
    )
    installment_start: NonNegativePeriod | None = Field(
        default=None,
        description="Zero-based project period of the first equal_installments repayment; required for that method after backend default resolution." + _FACILITY_DEFAULT,
    )
    installment_interval: PositivePeriod | None = Field(
        default=None,
        description="Positive number of model periods between equal_installments repayments; required for that method after backend default resolution." + _FACILITY_DEFAULT,
    )
    installment_count: PositivePeriod | None = Field(
        default=None,
        description="Positive number of equal principal repayments for equal_installments; required for that method after backend default resolution." + _FACILITY_DEFAULT,
    )


class FinancingFacilityInput(FinancingFacilityUpdate):
    """Facility source with optional backend-resolved preset fields.

    Optional fields intentionally have no MCP financial or product defaults.
    Serialization with exclude_none=True lets q_flow resolve them, while explicit
    zero amounts and false revolving flags remain contractual user inputs.
    """

    name: str = Field(
        min_length=1, max_length=128,
        description="Facility display name; required non-empty text, unique within the scenario.",
    )
    id: str | None = Field(
        default=None,
        description="Optional stable facility identifier retained in version-1 portable exports; omit/null to let q_flow assign one. Facility updates address the identifier separately and cannot change it.",
    )


class CashflowUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None, min_length=1, max_length=64,
        description="Scenario display name; omit on update to retain it. Explicit null is forwarded for backend validation.",
    )
    description: str | None = Field(
        default=None, max_length=1000,
        description="Scenario description in plain text; omit on update to retain it, use empty text to clear it. Explicit null is backend-validated.",
    )
    advance: Fraction | None = Field(
        default=None,
        description="Client advance as a fraction of contract value; 0.10 means 10%. advance + retention must not exceed one." + _CASHFLOW_DEFAULT,
    )
    retention: Fraction | None = Field(
        default=None,
        description="Fraction withheld from client progress invoices; 0.10 means 10%. advance + retention must not exceed one." + _CASHFLOW_DEFAULT,
    )
    release_retention_eop: Fraction | None = Field(
        default=None,
        description="Fraction of client retention released at the first/end-of-progress release point; the balance is released after dlp." + _CASHFLOW_DEFAULT,
    )
    dlp: NonNegativePeriod | None = Field(
        default=None,
        description="Defects liability delay in model periods between the first and final client retention releases." + _CASHFLOW_DEFAULT,
    )
    duration_for_payment: NonNegativePeriod | None = Field(
        default=None,
        description="Client invoice-to-payment delay in model periods; zero means no additional period delay." + _CASHFLOW_DEFAULT,
    )
    interest_rate: NonNegativeNumber | None = Field(
        default=None,
        description="Legacy scenario financing fraction per model period, used when no explicit financing facilities are configured; 0.005 means 0.5% per period. Convert annual quotes using the confirmed rate basis and periods/year (7% nominal annual with monthly periods is 0.07/12). Model periods do not inherently mean months." + _CASHFLOW_DEFAULT,
    )
    contract_value: NonNegativeNumber | None = Field(
        default=None,
        description="Main-contract value in currency units; zero is allowed. This is the lifetime client work value before timing effects." + _CASHFLOW_DEFAULT,
    )
    wieb: Fraction | None = Field(
        default=None,
        description="Work in Excess of Billings: fraction of completed client work carried to the next billing period. 0.20 means 20%; changes timing, not total contract value." + _CASHFLOW_DEFAULT,
    )
    use_independent_inflow_curve: StrictBool | None = Field(
        default=None,
        description="True selects the independent main-contract work curve when inflow_curve_type is non-null; false/null uses activity-linked inflow. Omit on creation for current backend defaults or on update to retain it.",
    )
    inflow_curve_type: InflowCurveType | None = Field(
        default=None,
        description="Independent main-contract curve: s_curve or linear. Explicit null selects legacy activity-linked inflow; omit on creation for the backend default or on update to retain it.",
    )
    inflow_curve_skew: CurveSkew | None = Field(
        default=None,
        description="Dimensionless independent S-curve skew strictly between -1 and 1; null is balanced zero and does not disable independent inflow. Retained but unused for linear curves; update omission retains it.",
    )


class CashflowInput(CashflowUpdate):
    name: str = Field(
        min_length=1, max_length=64,
        description="Scenario display name; required non-empty text, up to 64 characters.",
    )
    description: str | None = Field(
        default="", max_length=1000,
        description="Scenario description in plain text; omitted means an empty description. Null is accepted for legacy portable documents.",
    )
    financing_facilities: list[FinancingFacilityInput] | None = Field(
        default=None,
        description="Ordered financing source definitions, validated and resolved by q_flow. Omit/null/empty uses no explicit facilities and the legacy scenario interest model; source amounts, rates and schedules may be supplied per facility.",
    )
    activities: list[ActivityInput] = Field(
        default_factory=list,
        description="Source activities in this scenario; omitted means an empty scenario. q_flow normalizes schedules and recalculates all progress, cashflow and financing results.",
    )

    @model_validator(mode="after")
    def validate_percentages(self) -> "CashflowInput":
        if self.advance is not None and self.retention is not None:
            if self.advance + self.retention > 1:
                raise ValueError("cashflow advance + retention must not exceed 1")
        return self


class PortableCashflowDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["cashflowpot.cashflow"] = Field(
        default="cashflowpot.cashflow",
        description="Portable source-document format marker; only cashflowpot.cashflow is supported.",
    )
    version: Literal[1] = Field(
        default=1,
        description="Portable source-document version; only version 1 is supported, including its legacy activity fields and nullable curve settings.",
    )
    cashflow: CashflowInput = Field(
        description="Typed scenario source inputs, including activities and optional financing definitions; excludes calculated output and cashflow/activity ownership identifiers. Preserve omitted fields when importing so q_flow applies current defaults.",
    )
