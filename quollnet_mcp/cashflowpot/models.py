from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1000)
    color: str | None = None
    contract_value: float | None = Field(default=None, gt=0)


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    color: str | None = None


class ActivityInput(BaseModel):
    """Source activity fields accepted by q_flow.

    q_flow remains authoritative for the detailed mode/distribution validation.
    Manual Work and Scheduled Cost can provide cost_schedule_json instead of
    relying on generated cost curves.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    activity_type: str | None = None
    activity_mode: str | None = Field(default=None, description="work or scheduled_cost")
    distribution_type: str | None = Field(default=None, description="s_curve, linear, or manual")
    cost_schedule_json: dict[str, float] | list[float] | None = None
    cost: float | None = Field(default=None, gt=0)
    duration: int | None = Field(default=None, gt=0)
    duration_units: str | None = None
    start: int = Field(default=0, ge=0)
    advance: float | None = Field(default=None, ge=0, le=1)
    retention: float | None = Field(default=None, ge=0, le=1)
    release_retention_eop: float | None = Field(default=None, ge=0, le=1)
    dlp: int | None = Field(default=None, ge=0)
    duration_for_payment: int | None = Field(default=None, ge=0)
    work_in_excess: float | None = Field(default=None, ge=0, le=1)
    mobilization_period: int | None = Field(default=None, ge=0)
    subcontracted: float | None = Field(default=None, ge=0, le=1)
    skew: float | None = Field(default=None, gt=-1, lt=1)
    no_billing_period: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_source_shape(self) -> "ActivityInput":
        manual = self.distribution_type == "manual"
        scheduled = self.activity_mode == "scheduled_cost"
        if not (manual or scheduled) and (self.cost is None or self.duration is None):
            raise ValueError("generated Work requires cost and duration")
        if self.advance is not None and self.retention is not None:
            if self.advance + self.retention > 1:
                raise ValueError("activity advance + retention must not exceed 1")
        return self


class ActivityUpdate(ActivityInput):
    pass


class CashflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1000)
    advance: float | None = Field(default=None, ge=0, le=1)
    retention: float | None = Field(default=None, ge=0, le=1)
    release_retention_eop: float | None = Field(default=None, ge=0, le=1)
    dlp: int | None = Field(default=None, ge=0)
    duration_for_payment: int | None = Field(default=None, ge=0)
    interest_rate: float | None = Field(default=None, ge=0)
    contract_value: float | None = Field(default=None, ge=0)
    wieb: float | None = Field(default=None, ge=0, le=1)
    use_independent_inflow_curve: bool | None = None
    inflow_curve_type: str | None = Field(default=None, description="s_curve, linear, or null")
    inflow_curve_skew: float | None = Field(default=None, gt=-1, lt=1)
    financing_facilities: list[dict[str, Any]] | None = None
    activities: list[ActivityInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_percentages(self) -> "CashflowInput":
        if self.advance is not None and self.retention is not None:
            if self.advance + self.retention > 1:
                raise ValueError("cashflow advance + retention must not exceed 1")
        return self


class CashflowUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    advance: float | None = Field(default=None, ge=0, le=1)
    retention: float | None = Field(default=None, ge=0, le=1)
    release_retention_eop: float | None = Field(default=None, ge=0, le=1)
    dlp: int | None = Field(default=None, ge=0)
    duration_for_payment: int | None = Field(default=None, ge=0)
    interest_rate: float | None = Field(default=None, ge=0)
    contract_value: float | None = Field(default=None, ge=0)
    wieb: float | None = Field(default=None, ge=0, le=1)
    use_independent_inflow_curve: bool | None = None
    inflow_curve_type: str | None = None
    inflow_curve_skew: float | None = Field(default=None, gt=-1, lt=1)


class FinancingFacilityInput(BaseModel):
    """Facility source definition.

    The backend owns exact validation because the valid fields depend on draw and
    repayment methods. Extra fields are allowed so new q_flow facility options do
    not require an MCP release merely to pass them through.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=128)
    type: str = "Other"
    draw_method: str = "scheduled"
    repayment_method: str = "cashflow_sweep"
    start: int = Field(default=0, ge=0)
    end: int | None = Field(default=None, ge=0)
    limit: float | None = Field(default=None, ge=0)
    revolving: bool = False
    interest_rate: float = Field(default=0, ge=0)
    fees: float = Field(default=0, ge=0)
    sweep_priority: int | None = Field(default=None, ge=0)


class PortableCashflowDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str = "cashflowpot.cashflow"
    version: int = 1
    cashflow: dict[str, Any]
