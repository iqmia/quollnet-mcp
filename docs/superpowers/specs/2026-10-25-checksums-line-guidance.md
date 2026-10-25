> Historical implementation, superseded before deployment by server-tax-policy-qr. See current data guidance and the newer spec.

# MCP tax checks and canonical document lines

Implement the user's requested MCP checksum checks and unambiguous line-item
documentation with a typed schema. Keep QEntries' generic record JSON and backend
authority. No backend, database, fiscal certification or registry lookup changes.

Add a read-only check_qledger_tax_identifier tool in the selected authenticated
unit. Initially support PT NIF/NIPC: preserve original input, permit an explicit
PT prefix and ASCII spaces/hyphens for normalization, require nine ASCII digits
with nonzero first digit, weights9..2, mod11 and zero check digit for remainders0/1.
Return supported/status, normalized value, format/checksum results, expected and
supplied digits, weighted sum, warnings, blocking=false and verification_status=
unverified. Unsupported countries return unsupported, never a Portuguese result.
Do not silently correct identifiers, save records, assert existence/ownership,
certify VAT registration, block authorized storage or claim a platform rejection
without an actual rejection result. User-confirmed warnings can be recorded as
metadata while keeping external verification unverified.

Add read-only get_qledger_line_item_guidance in the authenticated unit. Use
Pydantic reference models for discriminated catalog/ad_hoc lines and document
data; expose JSON Schema and a complete canonical create-record example.
Canonical amounts are plain decimal strings, signed, below1e18 and up to12 decimal
places. Catalog lines require SKU/quantity; product_id/description/price may be
resolved from a confirmed existing product. Ad-hoc lines require description,
quantity, unit_price,total and no non-null product_id. Support optional discount,
tax, computed amounts, unit, project, cost_center and arbitrary supplementary
fields. Do not duplicate backend arithmetic or replace generic Record.data with
these reference types. Backend also accepts bounded numeric JSON and incomplete
drafts; document this distinction. Schema cannot prove product resolution, tax
facts or computed totals.

Approach: explicit advisory checker and on-demand schema/example tools. Prose-only
changes would leave calculations ad hoc; coercing all generic Record.data into
strict line models would break custom data/templates/partial drafts. Two new tools
make checks reproducible and reference types discoverable without changing writes.
