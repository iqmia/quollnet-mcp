> Historical implementation, superseded before deployment by server-tax-policy-qr. See current data guidance and the newer spec.

# MCP checksum and canonical line guidance review

Implemented two authenticated read-only tools: advisory PT NIF/NIPC checks and
on-demand canonical line documentation/schema. Generic record writes are unchanged.

Validation:
- Baseline:256 unittest tests passed.
- New feature tests initially failed for missing checksum/schema/tool behavior.
- Full pytest before final review fix:273 passed,499 subtests,8 baseline warnings.
- Final focused suite:18 passed,36 subtests.
- Final full unittest after review fix:274 passed (91.413s).
- New modules, modified production Python and new tests pass Ruff; new/reference
  modules and model changes pass formatting. An existing nested-context SIM117
  lint finding remains in test_qledger_workflows.py, outside the modified count.
- The canonical JSON example was replayed through actual QEntries SQLite
  prepare_document and validate_final_record with seeded WP-001. Product identity,
  negotiated unit_price20.00 and total280.00 were preserved; backend tree is clean.
- Tests exercise actual SDK discovery and structured output, readonly annotations,
  denied unit authorization, unsupported countries and unchanged generic PATCH
  transport after a failed checksum.

Independent review found one Important normalization issue: unrestricted strip()
accepted tabs/newlines/Unicode whitespace beyond the documented ASCII contract.
The regression failed for four such inputs before the fix; ASCII-only trimming
now passes them as invalid_format while legitimate spaces/hyphens remain accepted.
A minor model-serialization suggestion is addressed in the documentation: use
model_dump(mode="json", exclude_unset=True) for constructing payloads, rather than
including unset optional numeric nulls. Current tools return a clean canonical
example and JSON Schema; no reference-model payload construction is implicit.
No material findings remain and none are deferred.

Scope: Portuguese arithmetic only, never registry/ownership/VAT verification.
Other countries return unsupported. Warnings do not confer permissions or bypass
backend validation. No database migration, server deployment, live profile update
or merge was performed.
