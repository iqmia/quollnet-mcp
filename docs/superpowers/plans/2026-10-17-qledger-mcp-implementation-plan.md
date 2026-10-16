# QLedger MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing QLedger business API at `/qledger` through the connected user's normal QAuth permissions.

**Architecture:** Add a sibling `quollnet_mcp/qledger/` adapter using the completed shared core. QLedger retains all business validation, authorization, posting and cleanup. No QLedger product code or shared-core refactor is implemented on this planning branch.

**Tech Stack:** Existing Python, official MCP SDK, Starlette, httpx, Pydantic and unittest versions from the final integrated repository; no SDK/protocol upgrade or new runtime dependency is planned.

**Spec:** `docs/superpowers/specs/2026-10-17-qledger-mcp-design.md`

**Tool inventory:** `docs/superpowers/specs/2026-10-17-qledger-mcp-tool-map.md`

**Status:** Draft prepared at the user's request alongside the design. Implementation is not started. Reconcile against the finished CashflowPot/shared-core commit and have the written design/plan reviewed before execution. Do not execute against the old core merely because paths are listed below.

## Global Constraints

- Endpoint and OAuth resource: `https://mcp.quollnet.com/qledger`; separate audience from `/mcp` and `/cashflowpot`.
- Every unit tool requires an explicit `unit_id`; there is no process-global selected unit or token.
- Exchange at the time of the request; do not introduce a token cache in the first version.
- QLedger remains authoritative for token permissions, accounting, records, posting, links, attachments and recursive cleanup.
- Pagination defaults to 50, with `per_page` between 1 and 200.
- Use decimal strings for monetary values and exchange rates in tool schemas and JSON transport.
- Preserve the API's six decimal places for Money and ten for Rate, both with at most 20 digits; never round through binary floats.
- Require a caller-supplied `idempotency_key` of 1–128 characters on the keyed tools identified in the inventory.
- No automatic mutation retry in the initial client, including after token errors.
- Set `QLEDGER_MAX_FILE_BYTES=10485760` (10 MiB) by default and `QLEDGER_MAX_BATCH_FILE_BYTES=20971520` (20 MiB).
- Backend tokens and credential headers must never be returned to the model or logged.
- Records' `data` remains arbitrary finite JSON, not an invoice schema.
- Existing endpoint behavior must remain compatible; no live invitations or accounting writes during routine verification.

## Review Focus

1. A unit create/load response can contain credentials nested in a normal-looking payload: Task 2 pins allowlisted output shaping and no token in errors/logs.
2. Concurrent users/units can leak authority through global mutable state: Tasks 2 and 7 interleave exchanges and backend requests.
3. A lost keyed response and a stale evidence conflict require different handling: Tasks 2, 4 and 6 pin unknown-outcome guidance versus renewed review, with no automatic resubmission.
4. PATCH omitted/null fields and decimal JSON conversion can silently change accounting inputs: Tasks 1, 3 and 4 exercise precise serialization.
5. File size declarations and multipart aliases can be deceptive: Tasks 5 and 6 check actual streamed bytes, strict decoding, duplicate/unknown parts and aggregate limits.

## Integration prerequisite (before Task 1)

- [ ] Confirm the other process has finished and identify its final shared-core commit. Preserve its work; do not reset or force-push its branch.
- [ ] Inspect branch state, `AGENTS.md`, final `core/` exports, configuration, server factory, ASGI mount/metadata routing and lifecycle. Incorporate that commit into `feature/qledger-mcp` by normal history-preserving integration.
- [ ] Reconcile the shared paths in this plan (`core/config.py`, `combined_app.py`, existing central token exchange). These are dependency integration points, not permission to implement competing versions. If names differ, update this document and its references before code changes.
- [ ] Review the proposed file transfer with the intended MCP client: prove an existing base64-style upload can carry a real small invoice and the installed SDK/client supports authenticated binary-resource delivery. If it cannot, amend the design before implementing a different delivery mechanism.
- [ ] Read both spec documents; resolve any API drift from QLedger commit `92fc071e04583369e8d7746a91f3e16a59470c81`. Record the deployment URL/configuration separately; never guess it from the product name.
- [ ] Run the integrated baseline: `python -m unittest discover -s tests -v`. Record its result before adding QLedger. Use the repo's existing environment/setup procedure; no runtime dependency is needed for this documentation branch.

## Task 1: Typed request contracts and precision

**Files:** Create `quollnet_mcp/qledger/__init__.py`, `models.py`, `models_accounting.py`, `models_records.py`; test `tests/test_qledger_models.py`.

**Interfaces:**
- Common models: `PageQuery`, `DateQuery`, `LedgerQuery`, `TargetRef`, `RecordLinkCreate`, `VersionRequest`, `EvidenceManifest`, `FileInput(filename: str, content_type: str, file_base64: str)`.
- Accounting models: `AccountCreate`, `AccountPatch`, `SettingsCreate`, `SettingsPatch`, `LineCreate`, `JournalCreate`, `JournalPatch`, `PostRequest`, `ReversalRequest` mirror pinned API fields.
- Record models: `RecordCreate`, `RecordPatch`, `RecordPost`, `RecordQuery`, `OperationRef`, `OperationRecord`, `OperationAttachment`, `OperationLink`, `OperationRequest` mirror pinned API fields.
- `models.py`: `api_payload(model: BaseModel, *, patch: bool = False) -> dict[str, Any]`, `validate_idempotency_key(value: str) -> str`. Patch serialization preserves supplied null values and omits unsupplied fields. Amount/rate schema fields are strings parsed as finite Decimals for validation, emitted as strings.

- [ ] Write `test_decimal_transport`, asserting amount `"12345678901234.123456"` and rate `"1.1234567890"` survive unchanged, numeric float inputs/NaN/excess precision are rejected, and tool JSON schema uses string amounts.
- [ ] Write `test_patch_null_vs_omitted`, asserting RecordPatch version-only omits data/reference while explicitly supplied null includes them. Cover settings clearing locked_until_date and forbidden unknown keys.
- [ ] Write `test_operation_references`, asserting exactly one id/key, reserved journal key, unique aliases/file fields, record-only post_records, and post_journal requiring a new journal. Test UUID/date/currency/page bounds and arbitrary finite JSON records.
- [ ] Run `python -m unittest tests.test_qledger_models -v`; confirm missing-model failures. Implement only these API-shaped transport models and validators, not a second accounting engine.
- [ ] Run the same test module to green; commit `feat(qledger): define precise MCP request contracts`.

## Task 2: Delegated identity and safe backend client

**Files:** Create `quollnet_mcp/qledger/auth.py`, `qledger_client.py`, `tools/__init__.py`, `tools/units.py`; modify final shared config/dependency lifecycle; test `tests/test_qledger_client.py`, `tests/test_qledger_units.py`.

**Interfaces:**
- `auth.py`: `async application_token() -> str`, `async unit_token(unit_id: UUID) -> str`, using current authenticated MCP access-token context and the completed core exchange with QLEDGER_APP_ID. Credentials stay internal.
- `QledgerClient(settings)` is an async context manager. `async request(method: str, path: str, *, access_token: str, params: dict | None = None, payload: dict | None = None, idempotency_key: str | None = None) -> dict | list | None` is internal, accepts only adapter-built relative paths, and returns parsed JSON or None for204. Typed `QledgerClientError` retains status, safe details, outcome_unknown and retry guidance without request objects/credentials.
- `async multipart(path: str, *, access_token: str, fields: dict[str, str], files: dict[str, tuple[str, bytes, str]], idempotency_key: str) -> dict`; `async download(path: str, *, access_token: str, max_bytes: int) -> tuple[bytes, str]`.
- `tools/units.py`: exact nine names from tool inventory. UnitCreate and MemberInvite/MemberRoles follow API schemas; page arguments default50/max200. Create/load return only documented unit/hierarchy fields with credential fields excluded. All other outputs retain safe API data.

- [ ] Write `test_exchange_scope_and_concurrency`: no unit for app tools, exact unit for unit tools, two interleaved identities never share tokens; missing authentication never reaches QLedger.
- [ ] Write `test_client_mapping_and_errors`: fixed configured origin, encoded path IDs/role segments, bearer/key headers, JSON/multipart204 handling, 401/403/404/409/422 safe details, HTML rejection, timeout unknown outcome, and exactly one mutation attempt even on401/timeout.
- [ ] Write `test_unit_token_redaction` with create/load responses containing tokens and nested credential fields; assert no credentials in returned JSON/errors/logs. Pin allowlisted unit/hierarchy output shaping; do not blindly recurse arbitrary payloads into results.
- [ ] Table-test all nine unit tools against the inventory, including MemberInvite send_email=false/true forwarding without sending any real email. Test invitation timeout is unknown and not automatically retried.
- [ ] Run `python -m unittest tests.test_qledger_client tests.test_qledger_units -v`; confirm expected failures, implement the client/tools and target-specific settings, then rerun to green.
- [ ] Add .env.example settings only, never real values: QLEDGER_APP_ID, QLEDGER_BASE_URL, QLEDGER_TIMEOUT_SECONDS=30, QLEDGER_MCP_RESOURCE_URI and two file limits. Follow the finished core's enable convention so disabled QLedger does not break existing endpoints. Commit `feat(qledger): add delegated backend access and unit tools`.

## Task 3: Accounts, settings and authoritative reports

**Files:** Create `tools/accounts.py`, `tools/settings.py`, `tools/reports.py`; test `tests/test_qledger_accounting_tools.py`.

**Interfaces:** Exact four account, three settings and four report tool functions from the inventory. Each consumes explicit unit_id and the Task1 model/query for its route, returns API JSON, and obtains a Task2 unit token. No arbitrary HTTP proxy tool is exposed.

- [ ] Table-test all11 methods/paths, page/date/account query parameters and output shapes. Assert totals and decimal balances are returned from the backend without independent summation.
- [ ] Test account/settings PATCH sends version and only supplied fields, including explicit null. Account creation cannot patch immutable account type/normal balance; deactivation uses is_active.
- [ ] Run `python -m unittest tests.test_qledger_accounting_tools -v`; confirm missing-tool failures; implement named adapters. Test no automatic retry for unkeyed account creation/settings mutation.
- [ ] Rerun that module to green and commit `feat(qledger): expose accounts settings and reports`.

## Task 4: Drafts, posting, records and their links

**Files:** Create `tools/journals.py`, `tools/records.py`, `instructions.py`; test `tests/test_qledger_journals.py`, `tests/test_qledger_records.py`.

**Interfaces:** Exact seven transaction and eleven record functions from the inventory; typed body models from Task1 and idempotency_key only for the K-marked operations. `post_qledger_transaction(unit_id, entry_id, request: PostRequest)` and `post_qledger_record(unit_id, record_id, request: RecordPost)` never reconstruct approved evidence. The instructions explain preparation/review/post, permission roles, schema-free records and invoice lookup (including line-parent distinction).

- [ ] Table-test all18 routes and K headers. Assert get responses retain versions/evidence and mutation responses stay minimal when the backend omits content. No follow-up read enriches a blind mutation response.
- [ ] Write `test_stale_review_not_rewritten`: post returns409; assert exactly the supplied journal version and evidence were sent, no reload, no second attempt, and the tool error calls for review of changes. Repeat for record post and link-to-posted-parent review fields.
- [ ] Test decimal journal lines survive string JSON serialization; create/reverse return drafts; no automatic post. Test explicit lock override/reason, source-version copy, versioned record deletion, unversioned journal DELETE, atomic link replacement and 403 propagation.
- [ ] Test invoice queries forward exact parent pair/namespace/types/page; instruction tests state line-parent lookups are separate and template choice belongs to the caller. Do not generate a compulsory invoice schema.
- [ ] Run `python -m unittest tests.test_qledger_journals tests.test_qledger_records -v`; confirm expected failures; implement adapters and instructions; rerun to green.
- [ ] Commit `feat(qledger): expose reviewed transaction and record workflows`.

## Task 5: Shared attachments and authenticated binary delivery

**Files:** Create `files.py`, `tools/attachments.py`; test `tests/test_qledger_attachments.py`, `tests/test_qledger_files.py`.

**Interfaces:** `decode_file(file: FileInput, *, max_bytes: int) -> tuple[str, bytes, str]`; `async attachment_resource(unit_id: UUID, attachment_id: UUID) -> BlobResourceContents` uses Task2 unit token/client on every call. Exact eight attachment tools from inventory. Download tool returns metadata plus EmbeddedResource without duplicating blob text; server registration is completed in Task7.

- [ ] Test strict valid/invalid base64, data-URI rejection, no invented content, safe filenames, exact original bytes/digest and limit enforcement before decode. Pin10MiB file cap and streamed overflow abort even with missing/false Content-Length. Confirm no image conversion.
- [ ] Table-test all8 routes and canonical multipart fields. Upload requires K and initial parent, list requires target pair, replacement is one PATCH, unlink never triggers a separate MCP delete.
- [ ] Test `qledger://units/{unit_id}/attachments/{attachment_id}` read under two identities; each obtains its own token and backend authorization. After403/revocation, prior content is not served from a cache. No arbitrary URI/path fetch.
- [ ] Test binary resource includes MIME/URI/blob and no token or duplicate base64 ordinary text. Download errors/size limits return clear tool failures, not a fake public URL.
- [ ] Run `python -m unittest tests.test_qledger_attachments tests.test_qledger_files -v`; observe expected failures, implement bounded transport/resources, rerun to green. Commit `feat(qledger): add authorized shared attachment transfer`.

## Task 6: Atomic document registration with safe retries

**Files:** Create `tools/operations.py`; test `tests/test_qledger_operations.py`.

**Interfaces:** `async execute_qledger_operation(unit_id: UUID, operation: OperationRequest, idempotency_key: str, files: dict[str, FileInput] | None = None) -> dict[str, Any]`. File dict keys match OperationAttachment.file_field exactly; result is the backend OperationResult.

- [ ] Write invoice fixture with balanced new journal, invoice record, original file and explicit links; assert one multipart backend call with one payload field, exact file bytes and K. No tool-side rollback/create sequence occurs.
- [ ] Test no-file JSON path, extra/missing/reused file parts, reserved local keys/line aliases, strict aggregate20MiB limit and unchanged post flags. Reject duplicate multipart aliases before constructing the dict; model list validation must not silently collapse them.
- [ ] Test existing records posting through the new journal carry their exact version/reviewed file map. No automatic fetch fills missing approval; backend409 is surfaced unchanged.
- [ ] Test repeated calls forward the identical key/payload/bytes; changed-key conflicts remain409. After a simulated timeout, assert one attempt and guidance to retry the same payload/key; no generated substitute key. Compare returned local-key/ID maps exactly to backend output.
- [ ] Run `python -m unittest tests.test_qledger_operations -v`; confirm expected failures; implement atomic JSON/multipart adaptation; rerun to green. Commit `feat(qledger): support atomic invoice and evidence operations`.

## Task 7: Isolated endpoint, regressions and review handoff

**Files:** Create `server.py`, `tests/test_qledger_server.py`, `tests/test_qledger_workflows.py`; modify final ASGI composition/lifecycle, `readme.md` and existing CI configuration only as needed.

**Interfaces:** `build_qledger_server(settings) -> MCPServer` registers exactly47 tools and the Task5 resource reader, sets QLedger instructions, resource audience and OAuth security metadata. Assembly adds a single pooled QledgerClient lifecycle and QLedger session-manager lifecycle using the finished core convention. Concrete core imports are pinned by the integration prerequisite, not guessed during earlier tasks.

- [ ] Test exact47-name tool set, schemas and correct annotations; no QLedger tools leak to other endpoints and existing tool sets stay stable.
- [ ] Test `/qledger` initialize/list/call, exact slash handling, and no accidental `/qledger/mcp` requirement. Test401 challenge's resource metadata resolves correctly for this endpoint and existing endpoints; wrong-audience MCP tokens fail before exchange. Do not change accepted audiences globally to make tests pass.
- [ ] Test shared lifecycle opens/closes each client/manager once, disabled endpoint configuration, and interleaved users/units in assembled server requests.
- [ ] Run `python -m unittest tests.test_qledger_server tests.test_qledger_workflows -v`; confirm expected failures; register the server and integrate minimal mount/configuration changes after core is stable; rerun to green.
- [ ] Run `python -m unittest discover -s tests -v` and repository-required lint/CI checks. Preserve the passing CashflowPot/Quollnet baseline; fix failures attributable to this branch.
- [ ] Update README with connection URL, QAuth configuration prerequisites, tool families, permission-based roles, transfer caps/client limitations, reviewed posting and exact-key retry behavior. Verify documentation matches actual enabled configuration and deployment entrypoint.
- [ ] Review diff for accidental shared-core refactor, credentials, role-name authorization, hidden retries and public file URLs. Commit `feat(qledger): mount dedicated MCP and document integration`.
- [ ] With deployment and disposable-unit test actions authorized, verify creator/controller/accountant/auditor/admin combinations, invoice registration/retry/post/conflict/readback, parent-protected links and real client file delivery. Mock tests alone do not establish production readiness. Record observed results and any client limitation; do not claim deployed until deployment is verified.

## Execution handoff

Planning documents may be reviewed while CashflowPot work continues. Implementation waits for its finished shared core and the written design/plan review. Native execution is a reasonable choice here because the tasks share auth/client/model contracts; a whole-branch review should follow. Do not select or launch an execution method merely by reading this draft.
