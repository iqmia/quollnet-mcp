# QEntries MCP data checks and document lines

The MCP adapter provides two read-only tools in the selected authenticated unit:

- `check_qledger_tax_identifier(unit_id, identifier, country_code="PT")`
- `get_qledger_line_item_guidance(unit_id)`

Neither tool creates records, posts journals, issues documents or changes data.
Deploy this MCP change and refresh the ChatGPT connection to discover the tools.
No backend change or database migration is needed.

## Tax identifier checks

Initial support is **Portugal (PT), NIF/NIPC**. A generic TIN label does not identify
a country. Supply country_code explicitly; unsupported countries return
`status=unsupported_country`, with no invented algorithm or checksum result.

The tool preserves `identifier` exactly and returns `normalized_identifier`
separately. A PT prefix, ASCII spaces and hyphens can be removed for the
calculation; other letters/Unicode digits are not silently repaired. Basic format
requires nine ASCII digits with a nonzero first digit. Prefix allocation ranges
and taxpayer category are not checked.

For PT, multiply the first eight digits by 9 through 2, sum, and take modulo 11.
The expected digit is 0 for remainder 0/1, otherwise 11 minus the remainder. The
Portuguese regional-government [validation guide, pages2–3](https://proderam2020.madeira.gov.pt/images/documentos/Candidaturas/ACAPORAMA/Guia_de_validacao_M19.2.1.ii_a8b41.pdf)
documents this algorithm. Only the arithmetic is adopted; dated prefix-allocation
claims in that guide are not used.

For `517115897`, the tool returns `status=failed_checksum`, `weighted_sum=175`,
`expected_check_digit="1"`, `supplied_check_digit="7"`, `checksum_valid=false`.
For `501234567`, the expected check digit is 0; it also fails. Never replace either
identifier with a guessed correction merely because a different last digit would
pass the formula.

Every result has `blocking=false` and `verification_status=unverified`, even when
the checksum passes. This does not establish tax-authority registration, ownership,
VAT status or the existence of a taxpayer. No registry lookup is made.

When a user confirms storage of an identifier that failed the advisory check,
retain the supplied value and record the warning/confirmation as metadata if
requested. For example, metadata can contain:

```json
{
  "tax_validation_status": "failed_checksum_user_overridden",
  "verification_status": "unverified"
}
```

This documents acceptance of uncertain input, not a backend permission or fiscal
validation override. Backend permissions, immutable evidence and active unit
schemas still govern writes. Read the existing record/version first, preserve
unrelated fields when replacing its data JSON, save through ordinary CRUD and
verify the actual result. Distinguish backend errors, explicit platform rejections
and an operation that was never attempted. Never invent a safety-rejection cause
or announce an update before a successful tool response.

## Canonical transactional lines

Call `get_qledger_line_item_guidance` before creating/editing non-template
`invoice`, `purchase_order` or `quotation` data. The response includes the same
[typed JSON Schema](schemas/qentries-document-lines.schema.json) and
[canonical record example](examples/qentries-invoice-record.json) stored here.
Pydantic reference models live in `quollnet_mcp/qledger/models_lines.py`.
If constructing Python payloads from those models, serialize with
`model_dump(mode="json", exclude_unset=True)` so omitted optional fields remain
omitted; a default model dump includes unset numeric nulls and is not a canonical
write payload. The MCP guide already returns a clean canonical example.

The schema describes complete canonical **business data**, not every allowed
custom record or an entire issuance request. The existing CRUD/operation tools
continue accepting arbitrary finite JSON and partial drafts. Prepared printable
documents additionally need a suitable QTypeset layout in `data.rendering`; get
that contract from `get_qledger_document_design_guidance`. Business lines remain
in `data.lines`, separate from the rendering layout.

Example prerequisite: `WP-001` is a confirmed existing same-unit product, found
through `search_qledger_products`. Do not invent catalog SKUs. The example's zero
tax rate is illustrative; choose actual rates only from supported facts.

```json
{
  "type": "invoice",
  "is_template": false,
  "is_postable": true,
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
        "total": "180.00"
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
        "cost_center": "waterproofing.labour"
      }
    ],
    "subtotal": "300.00",
    "discount_amount": "20.00",
    "taxable_amount": "280.00",
    "tax_amount": "0.00",
    "total": "280.00"
  }
}
```

| Field | Catalog line | Ad-hoc line |
| --- | --- | --- |
| `line_id` | Required, stable and unique in document | Same |
| `line_type` | `catalog` | `ad_hoc` |
| `sku` | Required, case-sensitive product SKU | Not used for product resolution |
| `product_id` | Optional initially; use returned ID with SKU on later edits | Omit or null |
| `description`, `unit` | Backend snapshots verified product values | Description required; unit optional |
| `quantity` | Required | Required |
| `unit_price` | Negotiated price or omitted/null to use catalog default | Required |
| `total` | Optional input; checked if supplied | Required submitted value |
| Discounts/tax/computed amounts | Optional; omit unused numeric fields | Same |
| Supplementary fields | Retained (e.g. budget_code, source document/line IDs) | Same |

Canonical financial values are plain signed decimal **strings**: no binary-float
conversion, magnitude below 1e18, up to 12 fractional places. The reference schema
uses strings; the backend also accepts bounded numeric JSON and scientific
notation. Signed lines are valid. `currency_scale` is an integer 0..6 (default 2).

The backend rounds HALF_UP per line:

1. `subtotal = round(quantity * unit_price)`.
2. `discount_amount = round(subtotal * discount_percent / 100)`, or an explicit
   currency-precision `discount_amount` (default 0). On initial input use one
   discount method; normalized saved lines may contain both calculated fields.
3. `taxable_amount = subtotal - discount_amount`.
4. `tax_amount = round(taxable_amount * tax_rate / 100)` (omitted tax_rate means 0).
5. `total = taxable_amount + tax_amount`.

`discount_percent` must be 0..100; `tax_rate` must be 0..1000 percentage points (23
means 23%, not 0.23). Explicit discounts must reduce subtotal without exceeding its
magnitude. Submitted amounts and document-level sums must match backend arithmetic.
After editing quantity, price, tax or discount, recompute submitted totals.
Optional numeric fields should be **omitted**, not sent as null (catalog
unit_price is the exception). The reference schema does not prove arithmetic,
unique line IDs, actual products or legal tax treatment; QEntries remains the
validator. Extra line/document fields are allowed and retained. Schemas never
freeze live products: finalized documents keep their historical line snapshots.

Unresolved product drafts can be saved only with otherwise valid line values;
missing/empty lines or unresolved products cannot be finalized. If product
resolution refreshes the saved draft, review that new snapshot before issuance.
