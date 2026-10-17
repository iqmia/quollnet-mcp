from datetime import date
from pydantic import Field, model_validator
from .models import Schema, JsonData, PageQuery, TargetRef, VersionRequest
from .models_accounting import JournalCreate


class RecordCreate(Schema):
    type: str = Field(min_length=1, max_length=100)
    document_date: date | None = None
    reference: str | None = Field(default=None, max_length=255)
    data: JsonData
    links: list[TargetRef] = Field(default_factory=list, max_length=1000)


class RecordPatch(VersionRequest):
    type: str | None = Field(default=None, min_length=1, max_length=100)
    document_date: date | None = None
    reference: str | None = Field(default=None, max_length=255)
    data: JsonData = None


class RecordPost(VersionRequest):
    reviewed_attachments: dict[str, str]


class RecordQuery(PageQuery):
    linked_to_object: str | None = Field(default=None, min_length=1, max_length=100)
    linked_to_object_id: str | None = Field(default=None, min_length=1, max_length=255)
    linked_to_app: str = Field(default="", max_length=128)
    types: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def pair(self):
        if bool(self.linked_to_object) != bool(self.linked_to_object_id):
            raise ValueError("Supply both target type and ID")
        return self


class OperationRef(Schema):
    kind: str = Field(min_length=1, max_length=100)
    id: str | None = Field(default=None, min_length=1, max_length=255)
    key: str | None = Field(default=None, min_length=1, max_length=100)
    version: int | None = Field(default=None, ge=1)
    reviewed_attachments: dict[str, str] | None = None

    @model_validator(mode="after")
    def reference(self):
        if (self.id is None) == (self.key is None):
            raise ValueError("Use exactly one id or local key")
        return self


class OperationRecord(RecordCreate):
    key: str = Field(min_length=1, max_length=100)


class OperationAttachment(Schema):
    key: str = Field(min_length=1, max_length=100)
    file_field: str = Field(min_length=1, max_length=100)


class OperationLink(Schema):
    source: OperationRef
    target: OperationRef
    linked_to_app: str = Field(default="", max_length=128)
    relation: str = Field(default="", max_length=100)


class OperationRequest(Schema):
    records: list[OperationRecord] = Field(default_factory=list, max_length=1000)
    attachments: list[OperationAttachment] = Field(
        default_factory=list, max_length=1000
    )
    journal: JournalCreate | None = None
    links: list[OperationLink] = Field(default_factory=list, max_length=2000)
    post_journal: bool = False
    post_records: list[OperationRef] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def aliases(self):
        keys = [obj.key for obj in [*self.records, *self.attachments]]
        if (
            "journal" in keys
            or any(k.startswith("journal:") for k in keys)
            or len(keys) != len(set(keys))
        ):
            raise ValueError(
                "Local keys must be unique; journal and journal:line aliases are reserved"
            )
        fields = [a.file_field for a in self.attachments]
        if "payload" in fields or len(fields) != len(set(fields)):
            raise ValueError("Each attachment needs a unique non-payload file part")
        if self.post_journal and self.journal is None:
            raise ValueError("post_journal requires a new journal")
        if any(r.kind != "record" for r in self.post_records):
            raise ValueError("post_records accepts record references only")
        return self
