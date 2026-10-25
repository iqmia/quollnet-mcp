"""On-demand, typed canonical line guidance without changing generic CRUD."""

from typing import Any

from .models import Schema
from .models_lines import DocumentData


class LineItemGuidance(Schema):
    schema_version: str = "qentries-document-lines-v1"
    document_types: list[str]
    canonical_example: dict[str, Any]
    document_data_schema: dict[str, Any]
    rules: list[str]


def line_item_guidance() -> LineItemGuidance:
    return LineItemGuidance(
        document_types=["invoice", "purchase_order", "quotation"],
        canonical_example={
            "type": "invoice",
            "is_template": False,
            "is_postable": True,
            "data": {
                "currency": "EUR",
                "currency_scale": 2,
                "lines": [
                    {
                        "line_id": "line-1",
                        "line_type": "catalog",
                        "sku": "WP-001",
                        "quantity": "10",
                        "unit_price": "20.00",
                        "discount_percent": "10",
                        "tax_rate": "0",
                        "total": "180.00",
                    },
                    {
                        "line_id": "line-2",
                        "line_type": "ad_hoc",
                        "description": "Installation",
                        "quantity": "1",
                        "unit": "job",
                        "unit_price": "100.00",
                        "tax_rate": "0",
                        "total": "100.00",
                        "cost_center": "waterproofing.labour",
                    },
                ],
                "subtotal": "300.00",
                "discount_amount": "20.00",
                "taxable_amount": "280.00",
                "tax_amount": "0.00",
                "total": "280.00",
            },
        },
        document_data_schema=DocumentData.model_json_schema(),
        rules=[
            "Example prerequisite: WP-001 is a confirmed existing same-unit product. Search first; never invent a SKU. Zero tax here is illustrative, not tax advice or a default jurisdictional rate.",
            "The schema describes canonical complete data for non-template invoice/purchase_order/quotation instances. Keep business lines in data.lines; QTypeset layout goes separately in data.rendering.",
            "Every line has stable unique line_id and line_type=catalog|ad_hoc. Catalog requires sku and quantity; server resolves product_id/description/unit and missing price. Explicit negotiated prices stay unchanged. Ad-hoc requires description, quantity, unit_price,total and no non-null product_id.",
            "Canonical amounts are exact plain decimal strings, signed and below 1e18 with up to 12 decimal places. The backend also accepts bounded JSON numbers/scientific notation and incomplete drafts; generic Record.data is unchanged. Empty/missing lines and unresolved catalog products cannot be finalized.",
            "Round HALF_UP per line to currency_scale (0..6, default 2): subtotal=round(quantity*unit_price); discount=round(subtotal*discount_percent/100) OR currency-precision discount_amount (default 0); taxable=subtotal-discount; tax=round(taxable*tax_rate/100); total=taxable+tax. Supplied line amounts and document sums must match.",
            "Reference schema checks structure, not arithmetic, uniqueness, tax facts or product existence. QEntries is authoritative. Omit unused optional values rather than sending null for numeric discount/tax/computed fields. Preserve arbitrary supplementary line/document metadata.",
            "Quantity/price changes require recomputing any supplied totals. Use percentage points (tax_rate=23 means 23%, not 0.23); never infer a tax rate. Signed lines are supported. Products remain live; issued line snapshots are immutable.",
        ],
    )
