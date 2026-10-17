"""Transport types; QLedger remains authoritative for business validation."""
import json
from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictStr, TypeAdapter, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _money(value: str) -> str:
    TypeAdapter(Annotated[Decimal, Field(ge=0, max_digits=20, decimal_places=6, allow_inf_nan=False)]).validate_python(value)
    return value


def _rate(value: str) -> str:
    TypeAdapter(Annotated[Decimal, Field(gt=0, max_digits=20, decimal_places=10, allow_inf_nan=False)]).validate_python(value)
    return value


Money = Annotated[StrictStr, AfterValidator(_money)]
Rate = Annotated[StrictStr, AfterValidator(_rate)]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
RoleName = Annotated[str, Field(min_length=1, max_length=100)]


def finite_json(value: Any) -> Any:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("Record data must be finite JSON") from error
    return value


JsonData = Annotated[Any, AfterValidator(finite_json)]


def api_payload(model: BaseModel, *, patch: bool = False) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_unset=patch)


def validate_idempotency_key(value: str) -> str:
    value = value.strip()
    if not 1 <= len(value) <= 128 or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError("Idempotency-Key must be 1–128 printable ASCII characters")
    return value


class PageQuery(Schema):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)


class DateQuery(PageQuery):
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to")
        return self


class LedgerQuery(DateQuery):
    account_id: UUID | None = None


class TargetRef(Schema):
    linked_to_object: str = Field(min_length=1, max_length=100)
    linked_to_object_id: str = Field(min_length=1, max_length=255)
    linked_to_app: str = Field(default="", max_length=128)
    relation: str = Field(default="", max_length=100)


class VersionRequest(Schema):
    version: int = Field(ge=1)


class RecordLinkCreate(TargetRef):
    version: int | None = Field(default=None, ge=1)
    reviewed_attachments: dict[str, str] | None = None


class EvidenceManifest(Schema):
    records: dict[str, int]
    attachments: dict[str, str]


class FileInput(Schema):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", pattern=r"^[A-Za-z0-9!#$&^_.+\-]+/[A-Za-z0-9!#$&^_.+\-]+$")
    file_base64: str = Field(min_length=1, max_length=13981016, repr=False)


class UnitCreate(Schema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, min_length=1, max_length=50)
    parent_unit_id: UUID | None = None


class MemberInvite(Schema):
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=320)
    roles: list[RoleName] = Field(default_factory=list)
    send_email: bool = True
    next: str | None = Field(default=None, max_length=2000)


class MemberRoles(Schema):
    roles: list[RoleName] = Field(min_length=1)
