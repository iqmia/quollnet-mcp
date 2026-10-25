# Server tax policy and default verification QR review

Scope: supersede undeployed MCP-only checksum implementation, retain typed line guidance, centralize checks and unit policy in QEntries, document legal-party identity and default issued verification QR. All changes on feature/mcp-checksums-line-guidance; no merge/deployment.

Validation:
- MCP full unittest discovery: 269 passed.
- Backend complete SQLite suite: 452 passed, 6 PostgreSQL-only skips, 9 existing warnings.
- Backend focused tax/issuance/discovery/role regressions: 59 passed; independent review reran52 focused tests.
- Changed-file Ruff and git diff --check clean.
- Actual local QTypeset v2 renderer accepted updated default PO payload and generated a 4,779-byte PDF. Rasterized and visually inspected closing-area right-aligned QR; zxing-cpp decoded exact synthetic verification URL. No live service requests or production issuance.
- Existing issued bytes and custom layouts are preserved. Tests cover missing/unreferenced/wrong-type/custom QR placement and no live draft URL.

Independent review found and verified fixes for: null/non-object strict-policy bypass; exact-input output stripping; implicit issuer diagnostic read-permission leak; strict user business-schema compatibility. Additional executor regressions cover forged type/template audit imports, stale approval, policy edit/unlink permission, duplicate policy via PATCH, and legal-entity uniqueness/type invariants. Reviewer closed with no remaining blocking findings (52 independently run focused tests).

Catalog refresh only updates exact unchanged built-in v2 fingerprint on unit load; customized catalogs remain intact. No database migration. Existing QAuth units need updated role configuration/fresh tokens for record:tax_override; no permission is invented or inferred from role names. Foreign unsupported identifiers remain usable without override under strict policy. Canonical tax fields are documented; arbitrary legacy JSON is not guessed/migrated.
