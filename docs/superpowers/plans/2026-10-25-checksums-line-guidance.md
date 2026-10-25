> Historical implementation, superseded before deployment by server-tax-policy-qr. See current data guidance and the newer spec.

# MCP Checksums and Line Guidance Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans, inline.

**Goal:** Reproducible advisory PT checksum checks and typed canonical line guidance.
**Architecture:** Pure checksum module and Pydantic reference models, exposed by two
read-only authenticated MCP tools. Generic write schemas remain compatible.
**Tech Stack:** Existing Python/Pydantic/MCP SDK/unittest; no new dependencies.
**Spec:** docs/superpowers/specs/2026-10-25-checksums-line-guidance.md

## Global Constraints
- Advisory checks only; never mutate identifiers or declare tax-authority verification.
- Initially PT; unsupported countries are explicit. Preserve original supplied values.
- Reference schemas must match backend field names, signed decimals and extra fields.
- Keep custom record JSON, template/partial-draft compatibility and server validation.
- Separate feature branch and draft PR. No merge or deployment.

## Review Focus
- Remainders0/1, wrong digits, Unicode digits, malformed/prefixed input and unsupported countries.
- No implicit writes, registry calls, or false verified status on successful checksums.
- Catalog defaults versus mandatory ad-hoc fields and arbitrary line metadata.
- No float coercion, unsigned-only money restrictions or silent field loss.
- Actual MCP discovery/output schemas and invocation, not only Python helper calls.

## Task 1 — advisory checksum tool
Files: qledger/tax_identifiers.py, tools/guidance.py, server.py, tests/test_qledger_guidance.py.
- [x] Add failing known-valid/invalid/normalized/malformed/unsupported tests and tool discovery/call tests.
- [x] Implement check_tax_identifier and read-only check_qledger_tax_identifier with typed output.
- [x] Run focused tests and confirm structured results/annotations and authenticated unit scope.

## Task 2 — typed line guidance and documentation
Files: qledger/models_lines.py, line_guidance.py, tools/guidance.py, models_records.py,
server.py, instructions.py, docs/qentries-data-guidance.md, tests/test_qledger_guidance.py.
- [x] Add failing schema/example roundtrip, signed money, custom metadata, ad-hoc/catalog and generic-JSON compatibility tests.
- [x] Implement reference models and authenticated guidance tool; add canonical JSON and exact field rules.
- [x] Update registration-count expectations and instructions (including accurate error reporting).
- [x] Run full unittest/pytest suites and changed-file lint; review independently; publish draft PR.
