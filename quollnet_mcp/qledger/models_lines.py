"""Canonical input reference types; generic Record.data remains unrestricted JSON.

The backend also accepts bounded JSON numbers and partial drafts. These models
recommend exact plain decimal strings; product resolution/arithmetic stays there.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator
from pydantic.json_schema import SkipJsonSchema

# Up to 18 integer digits is strictly below 1e18; fractions have at most 12 places.
LineDecimal = Annotated[
    StrictStr,
    Field(
        pattern=r"^-?(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,12})?$",
        description="Exact signed decimal string; magnitude below 1e18; at most 12 decimal places.",
    ),
]
LineText = Annotated[StrictStr, Field(min_length=1, pattern=r"^\S(?:[\s\S]*\S)?$")]


# These values may be absent, but explicit null is not valid backend numeric input.
OmittableDecimal = LineDecimal | SkipJsonSchema[None]
NON_NULL_NUMBERS = frozenset(
    {
        "subtotal",
        "discount_percent",
        "discount_amount",
        "tax_rate",
        "taxable_amount",
        "tax_amount",
        "total",
    }
)


class ReferenceData(BaseModel):
    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def no_null_amounts(cls, value):
        if isinstance(value, dict) and any(
            key in value and value[key] is None
            for key in NON_NULL_NUMBERS & cls.model_fields.keys()
        ):
            raise ValueError(
                "Omit unused numeric fields; explicit null is not a number."
            )
        return value

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler(core_schema)
        for prop in schema.get("properties", {}).values():
            if prop.get("default", False) is None:
                prop.pop("default")
        return schema


class LineFields(ReferenceData):
    line_id: LineText = Field(
        description="Stable within the document; never change on reorder; unique per document."
    )
    quantity: LineDecimal
    unit: LineText | None = None
    project: LineText | None = None
    cost_center: LineText | None = None
    discount_percent: OmittableDecimal = Field(
        default=None,
        description="0..100 percent. Use this OR discount_amount on initial input; server validates calculated amounts.",
    )
    discount_amount: OmittableDecimal = Field(
        default=None,
        description="Currency-precision amount reducing subtotal; must not exceed its magnitude.",
    )
    tax_rate: OmittableDecimal = Field(
        default=None,
        description="0..1000 percent; zero if omitted. Supply only from supported tax facts.",
    )
    subtotal: OmittableDecimal = None
    taxable_amount: OmittableDecimal = None
    tax_amount: OmittableDecimal = None


class CatalogLine(LineFields):
    line_type: Literal["catalog"]
    sku: LineText = Field(
        description="Case-sensitive SKU from confirmed same-unit product search."
    )
    product_id: UUID | None = Field(
        default=None,
        description="Resolved same-unit Record.id; if supplied it must match SKU.",
    )
    description: LineText | None = Field(
        default=None,
        description="Backend snapshots verified product description on create/update.",
    )
    unit_price: LineDecimal | None = Field(
        default=None, description="Negotiated unit price; omit to use catalog price."
    )
    total: OmittableDecimal = Field(
        default=None, description="Backend calculates; any supplied total must match."
    )


class AdHocLine(LineFields):
    line_type: Literal["ad_hoc"]
    description: LineText
    unit_price: LineDecimal
    total: LineDecimal = Field(
        description="Required submitted total, checked against backend arithmetic."
    )
    product_id: None = Field(
        default=None, description="Ad-hoc lines cannot identify a catalog product."
    )


DocumentLine = Annotated[CatalogLine | AdHocLine, Field(discriminator="line_type")]


class DocumentData(ReferenceData):
    currency: StrictStr | None = Field(
        default=None,
        description="Explicit unit currency code; never infer tax treatment from it.",
    )
    currency_scale: int = Field(default=2, ge=0, le=6, strict=True)
    lines: list[DocumentLine] = Field(min_length=1, max_length=10000)
    subtotal: OmittableDecimal = None
    discount_amount: OmittableDecimal = None
    taxable_amount: OmittableDecimal = None
    tax_amount: OmittableDecimal = None
    total: OmittableDecimal = None
