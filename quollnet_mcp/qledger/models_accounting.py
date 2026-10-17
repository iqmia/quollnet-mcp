from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from .models import Schema, Currency, Money, Rate, EvidenceManifest, VersionRequest


class AccountCreate(Schema):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    account_type: Literal["asset", "liability", "equity", "revenue", "expense"]
    normal_balance: Literal["debit", "credit"]
    parent_id: UUID | None = None
    is_partner: bool = False


class AccountPatch(VersionRequest):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: UUID | None = None
    is_active: bool | None = None
    is_partner: bool | None = None


class SettingsCreate(Schema):
    base_currency: Currency
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    fiscal_year_start_day: int = Field(default=1, ge=1, le=31)


class SettingsPatch(VersionRequest):
    base_currency: Currency | None = None
    locked_until_date: date | None = None
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    fiscal_year_start_day: int | None = Field(default=None, ge=1, le=31)


class LineCreate(Schema):
    account_id: UUID
    debit: Money = "0"
    credit: Money = "0"
    description: str | None = Field(default=None, max_length=1000)
    currency: Currency | None = None
    foreign_amount: Money | None = None
    exchange_rate: Rate | None = None


class JournalCreate(Schema):
    transaction_date: date
    description: str = Field(min_length=1, max_length=2000)
    lines: list[LineCreate] = Field(min_length=2, max_length=1000)


class JournalPatch(VersionRequest):
    transaction_date: date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    lines: list[LineCreate] | None = Field(default=None, min_length=2, max_length=1000)


class PostRequest(VersionRequest):
    reviewed_evidence: EvidenceManifest
    override_lock: bool = False
    override_reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def override(self):
        if self.override_lock != bool(self.override_reason and self.override_reason.strip()):
            raise ValueError("A lock override requires explicit override_lock and a reason")
        return self


class ReversalRequest(Schema):
    transaction_date: date
    description: str = Field(min_length=1, max_length=2000)
