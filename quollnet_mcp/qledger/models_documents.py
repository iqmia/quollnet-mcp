from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from .models import Schema

PartName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")]


class PdfRenderRequest(Schema):
    version: int = Field(
        ge=1,
        description="Exact reviewed source record version; never substitute a new version after a conflict.",
    )
    asset_attachment_ids: dict[PartName, UUID] = Field(
        default_factory=dict,
        max_length=10,
        description="Image multipart part names mapped to authorized QEntries attachment IDs. Can instead be stored in record.data.rendering_assets.",
    )
    filename: str = Field(default="document.pdf", min_length=1, max_length=200)
    response_mode: Literal["metadata", "binary"] | None = Field(
        default=None,
        description="Saved draft previews default to metadata (no binary transfer); unsaved previews default to binary. Metadata requires save_to_record=true.",
    )
    save_to_record: bool = Field(
        default=False,
        description="Preserve the watermarked preview as a draft_pdf attachment on this draft record; requires record:link and an idempotency_key. Does not post anything.",
    )

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value):
        if any(c in value for c in "/\\") or any(
            ord(c) < 32 or ord(c) == 127 for c in value
        ):
            raise ValueError("Use a filename without paths or control characters")
        if not value.lower().endswith(".pdf"):
            raise ValueError("filename must end in .pdf")
        return value


class DocumentIssueRequest(Schema):
    version: int = Field(ge=1)
    asset_attachment_ids: dict[PartName, UUID] = Field(
        default_factory=dict, max_length=10
    )
    filename: str = Field(default="document.pdf", min_length=1, max_length=200)
    issuer_name: str | None = Field(default=None, max_length=255)
    reviewed_records: dict[str, int] = Field(default_factory=dict)
    reviewed_attachments: dict[str, str] = Field(default_factory=dict)

    _safe_filename = field_validator("filename")(
        PdfRenderRequest.safe_filename.__func__
    )


class DocumentStatusRequest(Schema):
    version: int = Field(ge=1)
    status: Literal["cancelled", "superseded"]
    reason: str = Field(min_length=1, max_length=1000)
