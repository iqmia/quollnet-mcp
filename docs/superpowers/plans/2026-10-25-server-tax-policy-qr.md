# Server tax policy and verification QR implementation plan

Goal: centralize tax checks in QEntries, retain canonical line guidance and default issued verification QR.
Architecture: country strategies + unit policy service, canonical party identity + internal audit, MCP HTTP forwarding; existing atomic issuer owns QR.
Spec: ../specs/2026-10-25-server-tax-policy-qr.md

- [x] Task 1: Test optional/required/foreign identifiers, explicit privileged override, stale audit, policy permissions and unit isolation; add services/tax_validation.py, schemas/tax.py, route and record integration. Recheck at finalization.
- [x] Task 2: Test unit_legal_entity uniqueness and settings protection; document canonical party/settings shape and update catalog/permissions.
- [x] Task 3: Test default/custom/malformed/unreferenced QR declarations and preview URL absence; adjust server rendering and seeded closing section.
- [x] Task 4: Replace MCP checksum algorithm with typed QEntries check request/response and forwarding tests; keep line guidance untouched. Update instructions/docs and counts if needed.
- [x] Task 5: Run both complete suites and changed-file lint; independent whole-change review, address material findings, publish draft PRs on named branch and inspect CI.

Review focus: unsupported foreign values accepted even under strict policy; no forged/stale approval; no policy weakening via type/links; explicit unit-bound reads; final QR actually referenced and correct type/server URL.

Validation ledger: backend452 pass/6 skips; MCP269 pass; changed-file lint clean; real local PDF QR rendered, visually inspected and decoded. Independent review closed. PR metadata carries remote CI outcome.
