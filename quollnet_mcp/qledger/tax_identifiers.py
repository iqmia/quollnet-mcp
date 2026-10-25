"""Typed QEntries tax-check contract. All validation/policy runs on QEntries."""

from typing import Annotated

from pydantic import ConfigDict, Field, StrictStr

from .models import Schema


class TaxIdentifierRequest(Schema):
    country_code: Annotated[StrictStr, Field(pattern=r"^[A-Za-z]{2}$")]
    identifier: Annotated[StrictStr, Field(max_length=128)] = ""
    identifier_type: Annotated[StrictStr, Field(min_length=1, max_length=32)] = "tax_id"


class TaxOverride(Schema):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=1000)


class TaxIdentifierCheck(Schema):
    country_code: str
    identifier: str
    identifier_type: str
    normalized_identifier: str
    supported: bool
    status: str
    format_valid: bool | None = None
    checksum_valid: bool | None = None
    algorithm: str | None = None
    weighted_sum: int | None = None
    expected_check_digit: str | None = None
    supplied_check_digit: str | None = None
    verification_status: str = "unverified"
    acceptance_status: str
    blocking: bool
    required: bool
    warnings: list[str]
    policy: dict
