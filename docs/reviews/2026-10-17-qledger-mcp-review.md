# QLedger MCP implementation review

Date: 17 October 2026. Branch: `feature/qledger-mcp`.

An independent read-only reviewer examined base `c16a50d0961a37767960ecdae9249fa998895962` through `28f6bab272c228ef228ef7b266459b7167783a15`, reran all 140 tests at that head and compared the relevant adapters with QLedger backend commit `92fc071e04583369e8d7746a91f3e16a59470c81` on GitHub. The older sibling local QLedger snapshot was not treated as authoritative.

## Findings and disposition

- **Important, fixed:** Backend downloads intentionally use `application/octet-stream`; the download tool now takes a validated original MIME from authorized attachment metadata and falls back to octet-stream. Resource-template reads deliberately remain generic. The backend-shaped MIME fixture failed before this fix and passed afterward.
- **Important after regrading, fixed:** Atomic-operation Pydantic errors use `detail.errors`. The client now retains bounded, sanitized location/message/type and excludes input/ctx/URL/other fields. A regression test containing sensitive rejected input failed before the fix and passed afterward. The reviewer initially rated this minor; it was regraded because normal backend-only accounting rejections otherwise lost the information a caller needs to correct a request. Cost of this ruling if wrong: an additional bounded error-format parser to maintain.

No critical findings, unaddressed important findings or deferred minor findings remain. The entire post-fix suite passes **141 tests**. Changed Python files pass Ruff F checks, formatting checks and `git diff --check`. One SDK/Pydantic schema-default warning also occurred in the 117-test pre-change baseline; no unrelated SDK upgrade was introduced.

## Implementation rulings

1. Reuse the completed `config.py`, `auth.py`, `services/qauth_client.py`, `dependencies.py` and `combined_app.py`; do not introduce a competing core directory. Reason: these are the interfaces the other process actually delivered. Cost if wrong: a later import migration.
2. Verify file exchange with the installed SDK and real ASGI transport against controlled upstreams; keep actual ChatGPT upload bridging/rendering as a deployment acceptance check. Reason: no live QLedger test unit, client file or deployment access was supplied. Cost if wrong: a client file bridge may be required before production acceptance.
3. Regrade the operation-validation finding as important and fix it, for the reason and maintenance cost above.

## Review edge-case rulings

These are dispositions of every behavior the reviewer considered but declined to classify as a defect. They record the scope and remaining uncertainty rather than asserting untested production behavior.

| Examined behavior | Ruling / reason | Cost if wrong |
|---|---|---|
| Actual ChatGPT PDF/image rendering and upload bridge | SDK protocol support is verified; intended-client acceptance stays open | Follow-up client bridge or delivery design |
| Live deployment, QAuth eligibility and backend parity | Deployment prerequisites remain explicit; no live writes were attempted | Deployment blocked until corrected |
| Balance/FX calculations, permissions, posted links and recursive cleanup | Keep these in QLedger; forwarding introduces no observed bypass | Backend defect must be fixed in QLedger |
| Existing-record review completeness in operations | Backend validates completeness; adapter preserves submitted snapshots | Backend rejection or backend validation defect |
| Encoded slash in role names | Safely encode the path segment; normal supported role names work, framework may reject slash names | Such a role may return not-found |
| Whitespace, reserved aliases and nullable inputs | Retain strict transport validation; observed differences reject inputs instead of silently altering accounting | Caller may need to normalize a rejected input |
| Generic resource-template MIME | Intentional SDK bytes callback; the download tool separately supplies original MIME | Generic resource reader may not preview inline |
| Independent file-hash recomputation | Backend owns immutable file identity/bytes; no second integrity layer added | A backend/storage integrity problem relies on its own controls |
| Partial streamed reads and authorization/limit failures | Bytes are bounded and uncached; failures do not return successful content | Upstream bytes may be consumed before failure |
| Compressed response allocation | No pinned backend download behavior demonstrated this concern; decoded transfer size remains checked | A future compressed backend could need streaming decompression hardening |
| Shared client cookie persistence | Inspected backend authorizes with explicit bearer tokens, not a cookie-derived identity | Reassess the client if backend starts using auth cookies |
| Factory-specific configuration and global dependency pools | Production uses one settings instance and one pool per service | Concurrent multi-configuration hosting would need dependency isolation |
| JWT audience-array semantics | Reuse the existing verifier; no signed multi-audience issuance/bypass observed | Reassess if QAuth begins issuing multi-resource tokens |
| Opaque secrets in arbitrary upstream prose | Known token/JWT/bearer redaction and fixed inspected backend messages suffice for current contract | New upstream error formats need a redaction review |
| Credential-looking content in allowed scalar unit fields or other responses | No such backend credential response was established; create/load nested credentials are excluded | A changed backend response contract needs renewed sanitization |
| Error bodies exceeding file transfer limits | Bound the body even if this replaces a detailed status error with a limit error | Less detailed error for that oversized response |
| Malformed successful unit responses | Backend validates its shape; unexpected shape yields a tool failure rather than invented data | Caller receives a generic failure until parity is restored |
| Separate machine-readable HTTP/outcome fields | Standard MCP error text retains status and unknown-outcome guidance; no additional client contract required | A future automated client may need typed fields |
| Whitespace around idempotency keys | Deterministic normalization matches QLedger and preserves retries | Callers must treat stripped-equivalent keys as the same key |
| Invocation annotations for access changes/unit loading | Hints represent intent and never replace backend authorization | Client presentation may be conservative |

## Release state

Implementation is complete on the feature branch; it is not merged or deployed. QLedger is disabled by default. Production needs its deployed HTTPS backend URL/application ID, eligible QAuth exchange registration, exact MCP resource registration, process restart and disposable-unit acceptance checks. Do not use real invitations or posted accounting entries as a discovery test.
