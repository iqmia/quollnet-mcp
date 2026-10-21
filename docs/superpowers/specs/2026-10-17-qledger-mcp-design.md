# QLedger MCP design

Date: 17 October 2026 (Asia/Beirut)
Status: Approved in conversation on 17 October 2026; implemented on feature/qledger-mcp. Deployment and real client file rendering remain to verify.

## Purpose and agreed scope

Add `https://mcp.quollnet.com/qledger` to `iqmia/quollnet-mcp`. An AI client acts through the connected user's QAuth identity and can perform all operations currently exposed by QLedger, subject to that user's actual application and unit permissions.

Examples include inviting a unit member, registering an invoice as a draft transaction with its original attachment and optional structured record, posting approved entries, and retrieving invoices or receipts linked to a transaction. Success means these workflows use the same authorization and business rules as any other QLedger caller.

The initial planning commit contained only this design, its tool mapping, and an implementation plan. Implementation was authorized after the CashflowPot work finished. It adds QLedger adapter code; QAuth settings, deployments, database schemas and the other process's branch are not changed. The written design and plan are review artifacts, not approval to deploy.

## Source baseline and integration dependency

- MCP planning branch: `feature/qledger-mcp`, based on `main` commit `015f6df7be8e06ad2a138de487719177c93f51de`.
- QLedger API examined: `quollnet/q_ledger`, `feature/records`, commit `92fc071e04583369e8d7746a91f3e16a59470c81`. Its presence on a branch does not establish production deployment.
- CashflowPot branch examined: `feature/dedicated-cashflowpot-mcp`, commit `226d2274bb8ee88b92095f15603fdd93df7772c9`. At that snapshot, `combined_app.py` assembles the MCPs; the proposed `core/` refactor is not yet present. Treat its final paths and exports as a dependency rather than assuming those interfaces exist.
- No `AGENTS.md` appeared in either inspected MCP tree. Check again after integrating the finished core work.

Implementation starts by incorporating the finished shared-core changes into this branch without rewriting the other branch. Reconcile source paths and update the plan before coding if its exported interfaces differ. Do not perform a competing shared-core refactor.

## Architecture and alternatives

Recommended: a sibling `quollnet_mcp/qledger/` package with a dedicated MCP server, a QLedger HTTP client, input models, file delivery, and focused tool modules. Reuse the completed shared authentication/configuration/token-exchange infrastructure. Only QLedger tools are registered on `/qledger`; existing `/mcp` and `/cashflowpot` tool sets stay compatible.

Adding everything to the general `/mcp` is simpler to mount but couples unrelated tools and instructions. A separate repository/service offers deployment isolation but duplicates infrastructure and operation. Neither is needed for the requested same-service endpoint.

Proposed package responsibilities:

| Path | Responsibility |
|---|---|
| `quollnet_mcp/qledger/server.py` | Build the QLedger MCP and register its tools/resources |
| `quollnet_mcp/qledger/auth.py` | Request-scoped use of the shared exchange service; never mint authority |
| `quollnet_mcp/qledger/qledger_client.py` | Fixed-origin HTTP requests, multipart bodies, errors, bounded downloads |
| `quollnet_mcp/qledger/models.py` | Common UUID/date/pagination, money, target, evidence and file inputs |
| `quollnet_mcp/qledger/models_accounting.py` | Account/settings/journal request models |
| `quollnet_mcp/qledger/models_records.py` | Generic records, links and operation graph request models |
| `quollnet_mcp/qledger/files.py` | Strict base64 conversion and authenticated binary-resource delivery |
| `quollnet_mcp/qledger/instructions.py` | Tool sequencing, document handling and review rules |
| `quollnet_mcp/qledger/tools/` | Units, accounts, settings, journals, reports, records, attachments, operations |

The plan names the post-refactor shared configuration as `core/config.py` and the ASGI assembly as `combined_app.py`. These are integration locations to confirm against the finished core, not instructions to create a second configuration or assembly system.

## Authentication and permissions

1. Client connects to `/qledger` using QAuth OAuth and the existing `mcp:connect` scope.
2. The endpoint verifies the MCP token's signature, issuer, lifetime, token kind, source application and exact audience `https://mcp.quollnet.com/qledger`. Tokens for `/mcp` or `/cashflowpot` are not interchangeable.
3. Reuse QAuth `POST /oauth/exchange-token` with `target_app_id=QLEDGER_APP_ID`. Omit `unit_id` for application-level unit discovery/creation/loading; include the explicit requested unit for business tools.
4. Send the resulting normal QLedger application/unit token to QLedger. Never send the raw MCP access token to its business API.
5. QLedger verifies the normal token locally and uses its `unit_permissions`. It also consults local invalidation markers. It does not call QAuth for each accounting permission check. Membership/unit administration and token operations still call QAuth because QAuth owns those operations.

Every unit tool requires an explicit `unit_id`; there is no process-global selected unit or token. Exchange at the time of the request; do not introduce a token cache in the first version. Simultaneous users and units must remain isolated. QLedger remains authoritative even if the MCP shows permissions for guidance.

QLedger's unit create/load APIs return tokens. Consume them internally and strip credential fields before returning anything to the model. Tokens, authorization headers, secrets and raw HTTP request objects must not enter tool results or logs. Unit load returns sanitized unit hierarchy; do not decode a returned token merely to expose permission context. If a future backend explicitly returns permission metadata, it can guide the assistant but is never an authorization decision in MCP.

Default role intent:

| Role | Responsibility |
|---|---|
| creator | Full unit and accounting access, expanded to concrete permissions by QAuth |
| admin | QAuth's common unit/member/role administration; no automatic accounting authority |
| accountant | Accounting preparation; excludes `journal:post`, `record:post`, `ledger:override_lock` |
| controller | All defined accounting/record capabilities, including posting and lock override |
| auditor | Read-only accounting and evidence access |

Role combinations are valid, such as admin + controller. Never infer grants from role names. Invitations require `invite:member`; controller alone does not imply that grant. Attachment access follows QLedger's authorized parent paths, not a blanket MCP attachment role.

QAuth prerequisites: add the exact `/qledger` resource to the central gateway's allowed MCP resources; allow central exchange for the QLedger target (`allow_quollnet_mcp_exchange=true`). Current exchange policy accepts open/shared-key targets, requires an active AppUser for shared-key apps, and excludes invite-only/closed targets. Do not weaken this policy; confirm QLedger's registration is eligible during rollout. Resource metadata and challenges must identify `/qledger` correctly even with other MCPs mounted on the same host.

## Tool surface and input contracts

The complete route-to-tool inventory is in `2026-10-17-qledger-mcp-tool-map.md`. Expose named, typed tools rather than an arbitrary URL/method HTTP proxy. All routes go through QLedger, including membership operations it proxies to QAuth. Unit deletion/editing, arbitrary permission editing and an attachment delete endpoint are not in the inspected QLedger API and must not be invented in MCP.

Mirror the API request contracts, including explicit versions on patches, posting, record deletion and copy. PATCH serialization uses only supplied fields so omitted and explicit null remain distinct. Strict models reject unknown keys, invalid IDs and nonfinite JSON. Records' `data` remains arbitrary finite JSON, not an invoice schema. Pagination defaults to 50, with `per_page` between 1 and 200; retain returned totals/pages and never imply that the first page is a complete report.

Use decimal strings for monetary values and exchange rates in tool schemas and JSON transport. Preserve the API's six decimal places for Money and ten for Rate, both with at most 20 digits; never round through binary floats. Dates are ISO dates; currencies are three uppercase letters. QLedger owns accounting validation, calculations, lock dates and persistence.

## Documents, records, links and cleanup

QLedger stores and returns generic caller-defined records. The caller selects invoice/receipt/order structure using its own code, an explicitly chosen template record, or a consciously selected latest-record fallback. MCP does not enforce a saved invoice schema or generate an official invoice layout inside QLedger.

Find an invoice for transaction X using record and attachment queries with `linked_to_object=journal_entry`, `linked_to_object_id=X`, and the required record `types` filter (for example `invoice,receipt`). If the workflow needs line-level evidence, inspect the entry's returned line IDs and query those parents as well. Do not imply entry-parent filtering also covers lines or arbitrary descendants. Return only backend-authorized content and links.

Records and attachments may have multiple parents. Native accounting objects belong to the authenticated QLedger application/unit; `linked_to_app` is an external reference namespace, not an alternate authorization scope. Posted record content is immutable. A record's link to an unposted parent can still change when the backend permits it, even if another posted transaction made the record immutable. Links to posted accounting parents remain protected. Attachments themselves are always unposted and their file bytes/identity are immutable.

Removal/deletion behavior is entirely backend-owned: after a parent deletion or unlink, an affected child is deleted only if unposted and parentless; recurse only into children of actually deleted objects. Shared or posted children survive. No MCP sweep or independent attachment deletion is added.

## Review, concurrency and posting

The assistant prepares and explains the intended transaction/documents for user authorization. Existing user instructions may authorize an action; do not add a separate MCP confirmation database or mandatory extra confirmation for every tool.

- Existing journal posting sends the reviewed journal `version` and exact `reviewed_evidence` (`records: ID -> version`, `attachments: ID -> SHA256`).
- Existing record posting sends its reviewed `version` and `reviewed_attachments` map.
- Linking an existing draft record to a posted accounting object supplies the reviewed source version and attachments when required by QLedger; it can post that record.
- Atomic operations may create records, a new journal, files, explicit links and requested posting together. The authorized proposed payload is the review boundary for new objects. Existing records that will post must carry the exact reviewed version/file map in their operation references, including when linked to a new journal being posted.
- Never fetch a fresh version/evidence manifest and automatically replace a rejected reviewed one. Surface 409 as a change requiring reload and renewed review of the differences.
- Corrections to posted accounting use new reversal/correcting entries. A reversal is prepared as a new draft and still needs an authorized posting step.
- Period-lock override remains explicit (`override_lock`, nonempty `override_reason`) and separately permission-checked. Never enable it to make a rejected request pass.

An atomic operation is one backend request, not a sequence of tool-side creates with attempted rollback. It supports a new journal, not arbitrary edits to an existing journal. Never silently decompose or simplify a failed batch.

## Idempotency and errors

Require a caller-supplied `idempotency_key` of 1–128 characters on create/reverse journal, create/copy record, create evidence link, upload attachment and execute-operation tools; transmit it as `Idempotency-Key`. The same user intent retried after a lost response uses the same key, payload, source IDs, flags and file bytes. An intentional changed request uses a new key. QLedger owns durable receipts; do not recreate them in MCP.

No automatic mutation retry in the initial client, including after token errors. Return a concise structured tool error identifying the HTTP status, safe backend validation details, and whether the result may be unknown after transport failure. Safe read retries may be added only with a fixed bounded policy; the first version sends once. For timeout after a keyed mutation, instruct retry with the unchanged request/key. For unkeyed mutations (unit/account creation or invitation, for example), report unknown outcome and inspect state before resubmitting. Do not claim exactly-once behavior on endpoints that lack receipts.

Preserve 401 (expired/stale), 403, 404, 409 and 422 distinctions. Missing permissions must never trigger elevated credentials or an alternative unit. Do not populate a minimal record mutation response with content fetched under another identity. Serialize backend-provided data without synthesizing hidden fields. Safe validation details are filtered by an allowlist; arbitrary upstream HTML, credential values and request headers are excluded.

## File transfer proposal

Use the repo's existing strict base64 upload convention initially: filename, MIME type and `file_base64`, decoded to multipart bytes. Preserve originals; no WebP conversion, OCR overwrite or content rewriting. The caller must supply actual accessible bytes; the model must never invent file content from an invoice description. File references from a client are not assumed to be server-readable paths.

Set `QLEDGER_MAX_FILE_BYTES=10485760` (10 MiB) by default and `QLEDGER_MAX_BATCH_FILE_BYTES=20971520` (20 MiB). Enforce encoded input limits before decoding, per-file and aggregate decoded limits, safe filenames and valid base64. QLedger/proxy limits may be lower and remain authoritative. This proposal deliberately bounds transfer size; it does not promise unlimited uploads.

Authenticated download returns filename/MIME/hash metadata plus an embedded binary MCP resource (`BlobResourceContents`), using URI `qledger://units/{unit_id}/attachments/{attachment_id}`. Register the corresponding resource reader with the same request-scoped identity and backend authorization as the tool; no unauthenticated resource cache. Bounded streaming aborts oversized responses. Content remains base64 in the binary resource field, not duplicated into ordinary text/structured content. Do not present the backend's bearer-protected URL as a public browser download, and do not put bearer tokens in URLs.

Client rendering varies. Before implementation is accepted, test the intended MCP client with a real small invoice upload and PDF/image download. If that client cannot transfer/display these supported shapes, agree a file-reference bridge or authenticated short-lived download design before claiming end-to-end file support. Signed browser URLs and arbitrary remote-URL fetching are excluded from this initial plan; they would require a separate reviewed interface, not a silent public-file fallback.

## Configuration, deployment and verification

Add target-specific `QLEDGER_APP_ID`, `QLEDGER_BASE_URL`, `QLEDGER_TIMEOUT_SECONDS` (default 30), `QLEDGER_MCP_RESOURCE_URI` (default `https://mcp.quollnet.com/qledger`) and the two byte limits through the finished shared configuration. The base URL is an explicit deployment value, not a guessed domain. Fail clearly when QLedger is enabled without its required settings. Use the existing endpoint-enable convention; unrelated endpoints must not acquire an unconditional QLedger configuration dependency.

Keep one pooled async QLedger HTTP client with controlled startup/shutdown. Share infrastructure, not user tokens. Mount `/qledger` before any catch-all route. Verify exact path and slash behavior plus OAuth metadata routing; do not accidentally expose only `/qledger/mcp`. Follow the finished core's composition and lifecycle convention.

Tests must cover every mapping, input serialization, cross-user/unit isolation, wrong-audience rejection, token redaction in unit responses, permissions and partial write responses, exact evidence forwarding, unchanged-key retry guidance, atomic multipart mapping, file bounds/resources and errors. Existing Quollnet and CashflowPot suites must pass after integration. The MCP tests verify the adapter; QLedger's own backend suite remains the source of business-rule tests.

Rollout order: finish/integrate shared core; approve/reconcile this design and plan; verify deployed QLedger matches the documented API; configure eligible QAuth target/resource; implement and run adapter/regression tests; review deployment changes; then perform authorized end-to-end smoke tests in a disposable unit. Do not send live invitations or post accounting entries merely to test discovery.

## Acceptance workflows

1. Two users connect concurrently and see only their own allowed units/data.
2. Accountant registers an invoice attachment plus optional structured record and balanced draft transaction in one operation; retrying the exact key does not duplicate it.
3. Controller posts the reviewed journal/evidence. Editing or unlinking protected evidence is rejected; changed evidence before posting returns a review conflict.
4. Auditor retrieves authorized records/files/reports and receives normal denials for writes.
5. Admin invites/manages members where the token grants it; admin alone cannot gain posting authority through MCP.
6. A document linked to multiple objects remains retrievable from its authorized parents; unlinking follows backend orphan/protection rules.
7. The supported client completes real bounded file upload/download; unsupported rendering is reported rather than claimed as a successful user download.
8. `/mcp` and `/cashflowpot` continue working with their own tools and audiences.

## References

- QLedger API, schemas, `auth/qauth.py`, `auth/permissions.py` and `qauth_roles.json` at the pinned source commit above.
- QAuth `design-docs/mcp-authentication-implementation.md` and `q_auth/common_roles.json` on `iqmia/q_auth/master` (reviewed 17 October 2026).
- MCP OAuth discovery/audience requirements: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization (reviewed 17 October 2026; follow the repo SDK's negotiated protocol revision).
- MCP binary resource and embedded-result types: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-06-18/schema.mdx . Rendering is client-dependent; this design does not require an SDK/protocol upgrade.

## Implementation integration notes

The finished CashflowPot work was merged from main commit `c16a50d0961a37767960ecdae9249fa998895962` into this feature branch. It retained `quollnet_mcp/config.py`, `auth.py`, `services/qauth_client.py` and `dependencies.py`; these existing shared interfaces are reused. No parallel core directory was introduced.

QLedger is optional (`QLEDGER_ENABLED=false` by default). The combined ASGI factory mounts it before the legacy catch-all when enabled, normalizes its exact no-slash path internally and exposes its RFC resource-metadata route at the host root.

The installed SDK's resource-template callbacks consume bytes. Resource reads therefore advertise `application/octet-stream`; `download_qledger_attachment` returns the specific upstream MIME type as an embedded binary resource plus filename/hash metadata. Neither path caches authorized file bytes or requires public download URLs. Transfers have a hard per-file schema ceiling of 10 MiB; the deployment can configure a lower limit.

Automated tests cover actual ASGI/MCP transport, signed MCP tokens, per-request QAuth exchange, two concurrent users/units and binary resource reads using controlled upstream HTTP transports. These tests do not establish live QLedger deployment or ChatGPT file-rendering support. The live acceptance workflows remain deployment checks.
