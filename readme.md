# Quollnet MCP

Standalone MCP gateway using the official `mcp==2.0.0` SDK.

The production process exposes two independent MCP resources while sharing the
same QAuth client, backend HTTP clients, and process:

```text
https://mcp.quollnet.com/mcp          existing Quollnet MCP
https://mcp.quollnet.com/cashflowpot  dedicated CashflowPot MCP
```

The existing `/mcp` tool surface is intentionally unchanged. CashflowPot's full
tool surface is registered only on `/cashflowpot`.

## Install

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

For the combined production-compatible application:

```powershell
.\.venv\Scripts\python.exe -m uvicorn combined_app:app --reload
```

The existing `app:app` entrypoint remains available when only the legacy
Quollnet MCP is wanted.

Local endpoints with the combined application are:

```text
http://127.0.0.1:8000/mcp
http://127.0.0.1:8000/cashflowpot
http://127.0.0.1:8000/health
```

Configuration is environment-based. Copy `.env.example` to `.env` and export
the values in your shell before starting Uvicorn.

Production-specific values include:

```text
MCP_RESOURCE_URI=https://mcp.quollnet.com/mcp
CASHFLOWPOT_MCP_RESOURCE_URI=https://mcp.quollnet.com/cashflowpot
QFLOW_BASE_URL=https://cashflowpot.com/api/
```

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Authentication and authorization

The Quollnet MCP OAuth token establishes the connected QAuth identity. For a
target application, the MCP exchanges that identity through QAuth for the same
normal application or user/unit token that the target application already
understands.

The two MCP resources use separate JWT audiences even though they share the same
QAuth source identity and token-exchange implementation:

```text
/mcp          aud=https://mcp.quollnet.com/mcp
/cashflowpot  aud=https://mcp.quollnet.com/cashflowpot
```

A token minted for one resource is not accepted by the other.

The MCP does not maintain a parallel application-permission model. Target
applications remain authoritative for their own roles, permissions, validation,
and persistence. qApp interprets its normal application roles; q_flow interprets
normal CashflowPot project/Unit permissions.

QAuth's canonical token-exchange design is maintained in:

`iqmia/q_auth/design-docs/mcp-authentication-implementation.md`

## QArticles

QArticles tools exchange the connected MCP identity for a normal qApp user
token. qApp therefore remains authoritative for article ownership, author/admin
permissions, validation, publication state, and persistence.

The MCP server advertises concise cross-tool workflow instructions to connected
models. These instructions guide tool sequencing; they do not grant permissions
or replace qApp validation.

Article-authoring rules are deliberately not duplicated in this repository.
Before creating or substantially rewriting a QArticle, the assistant should call
`get_article_authoring_policy` and follow the policy returned by qApp. The
canonical source is:

`iqmia/qApp/contracts/articles/article_authoring_policy.v1.md`

Important integration rules include:

- creating a QArticle creates an unpublished draft;
- `primary_article_topic` is separate from `article_topics`, which contains only
  additional topics;
- an existing article slug is preserved unless the user explicitly asks to
  change it, including grandfathered legacy slugs;
- targeted article requests should produce targeted edits rather than unrelated
  rewrites;
- qApp's lifecycle and health checks remain authoritative for publication
  readiness;
- MCP must not hard-delete QArticles or silently perform bulk link replacements.

## CashflowPot

The dedicated CashflowPot resource exchanges the connected MCP identity for a
normal CashflowPot app token for discovery/project creation and for a normal
CashflowPot Unit token for project-scoped operations. `q_flow` remains
authoritative for Unit permissions, validation, persistence, all calculations,
and returned KPIs.

CashflowPot financing facilities remain embedded inside the cashflow scenario so
the canonical JSON scenario is portable. The MCP exposes individual facility
tools only as convenience operations; those tools call q_flow's atomic facility
routes and never create a second facility persistence model.

The dedicated resource exposes the complete user-facing groups:

```text
Projects     list/get/create/update/delete/restore/hard-delete
Cashflows    get/results/create/update/delete/restore/hard-delete/import/export JSON
Activities   types/get/create/update/delete/restore/restore-many/hard-delete/deleted-list
Facilities   presets/list/get/add/update/delete/order
Exports      Excel
```

CashflowPot percentages are fractions (`0.10` means 10%) and backend period
indexes are zero-based. MCP tools forward source inputs and never reproduce the
financial calculation engine.

### Excel export

The Excel tool calls q_flow for short-lived signed download metadata. MCP does
not download or base64-encode the workbook. Opening the returned URL causes
q_flow to validate the signed token, load the current authoritative cashflow,
generate the XLSX in memory, and stream it to the caller. Generated workbooks
are not retained on either server.

### Production QAuth configuration

No new q_auth code is required. The existing QAuth MCP source application must
include this exact resource URL:

```text
https://mcp.quollnet.com/cashflowpot
```

The CashflowPot target application must continue to allow Quollnet MCP token
exchange (`allow_quollnet_mcp_exchange=true`). Application and Unit permissions
remain authoritative after exchange.

## QLedger

The same `combined_app:app` process can additionally serve the dedicated MCP at
`https://mcp.quollnet.com/qledger`. It exposes 51 named tools for units/members,
accounts/settings, transactions/reversals/posting, reports, records, shared
attachments and atomic document registration. Existing `/mcp` and `/cashflowpot`
tool sets remain separate.

Enable this optional endpoint in the deployment environment:

```dotenv
QLEDGER_ENABLED=true
QLEDGER_APP_ID=<the-existing-QLedger-QAuth-application-ID>
QLEDGER_BASE_URL=<the-deployed-QLedger-HTTPS-service-root>
QLEDGER_MCP_RESOURCE_URI=https://mcp.quollnet.com/qledger
QLEDGER_TIMEOUT_SECONDS=30
QLEDGER_MAX_FILE_BYTES=10485760
QLEDGER_MAX_BATCH_FILE_BYTES=20971520
```

The base URL can include the backend's deployment path prefix; the adapter appends
`api/...`. It must use HTTPS without credentials, query or fragment. Required
QLedger settings are checked only when enabled; disabled deployments continue
serving their existing MCPs. Restart the process after configuration changes.

In QAuth, register the exact `/qledger` MCP resource on the central gateway and
allow exchange into the QLedger target (`allow_quollnet_mcp_exchange=true`). The
current central exchange policy permits eligible open/shared-key targets; a
shared-key target requires existing active AppUser access. It excludes closed
and invite-only targets. Do not change those policies merely to make a failed
connection succeed. The deployed QLedger API must include the approved records
and shared-attachments implementation.

The connected MCP identity is exchanged for normal QLedger application/unit
tokens. QLedger validates signed token permissions locally (including local
invalidation markers); QAuth owns token exchange and unit/member administration.
No admin credential or model-supplied token is used. Every unit tool has an
explicit unit_id, and token-bearing unit responses are sanitized.

Roles bundle permissions: accountant prepares, controller posts, auditor reads,
and admin manages unit access. Admin does not automatically get accounting
posting authority; admin + controller is a valid combination. Actual token
permissions, including invite:member and journal:post/record:post, decide access.

Creation/reversal/link/upload/batch tools that require `idempotency_key` send it
to QLedger unchanged. After a lost response retry the same key, payload and
original file bytes. There are no automatic mutation retries. An unkeyed mutation
timeout has an unknown outcome: inspect state before resubmitting. A 409 review
conflict requires reloading and reviewing changes; the adapter never substitutes
fresh versions/hashes or silently enables a period-lock override.

Transaction posting requires its reviewed version and exact reviewed_evidence.
Record posting requires its reviewed version, reviewed_records descendant-version
map and reviewed_attachments hashes for the full subtree. Atomic
operations support a new journal, optional records/files and explicit links;
post flags remain explicit, and existing records that may post carry their
reviewed source evidence. QLedger enforces posting, immutable content, protected
links, parent-derived file access and recursive orphan cleanup. Generic records
have caller-defined finite JSON data; approved unit-linked record schemas can
validate templates and instances independently. QLedger does not render layouts.

File uploads use original-byte base64 without a data-URI prefix. They do not
convert images. The maximum per-file schema size is 10 MiB (configurable lower);
the default aggregate batch limit is 20 MiB. Downloads return filename/hash
metadata plus an embedded binary resource with its specific MIME type. The
resource reader `qledger://units/{unit_id}/attachments/{attachment_id}` returns
bytes as application/octet-stream and checks current authorization on every read.
Protected backend URLs and bearer tokens are never presented as public downloads.

Binary-resource rendering and chat-file upload integration depend on the client.
Before live acceptance, verify a real small invoice upload and PDF/image download
in the intended client. Automated SDK/ASGI tests verify the protocol adapter with
controlled upstreams; they do not prove ChatGPT rendering or production access.

Design, route-to-tool inventory and implementation plan are under
`docs/superpowers/{specs,plans}/2026-10-17-qledger-mcp-*`.

### Record templates and reversible posting (21 October 2026)

Requires QEntries migration `0004` and its corresponding API. The dedicated server
now registers 48 tools, including `unpost_qledger_record`. Accounting journals
remain permanently posted. Record unposting requires `record:post`, the current
version, and no posted record/journal/line parent. It affects only that record.
Posting or linking beneath a posted record also protects all record descendants;
review their versions and attachment hashes before submitting the request.

`is_template` is available in record create/PATCH/query and atomic records.
Use the ordinary type (`invoice`, `quotation`) for both templates and instances,
with the flag distinguishing them. Copy preserves the flag. Link adopted templates
to the unit and resolve document aliases from its catalog. `relation` remains a
caller-defined descriptive label. Template family/design version selection and
document composition are client responsibilities; attach issued PDFs for exact
reproduction. The rendering tools below call QEntries, which delegates to QTypeset.

### Document design and PDF rendering

Deploy the matching QEntries PDF API before using these tools. Configure
`QTYPESET_API_KEY` and optional `QTYPESET_BASE_URL` on the QEntries server, never
in this gateway or ChatGPT. There is no local PDF engine or fallback generator.
This addition requires no new database migration.

`get_qledger_document_design_guidance(unit_id, include_schema=true)` loads advisory
design defaults and the native v2 schema. Typography, restrained table styling,
plain issued-by/to blocks without section bars, images and pagination are covered.
User design preferences override these defaults within QTypeset capabilities.

The AI saves a complete native document in `record.data.rendering` (or directly
in `record.data`), with historical values and any image attachment bindings in
`record.data.rendering_assets`. Native asset `file` names map to authorized
QEntries attachment IDs. QEntries sends original PNG/JPEG bytes as multipart.

`render_qledger_record_pdf` takes the exact reviewed record version. By default it
returns a preview as embedded PDF bytes without changing the record. Set
`save_to_record=true` with a stable `idempotency_key` to preserve the PDF as an
ordinary attachment on a draft record; record:view and record:link are required.
Retries reuse that same PDF. Rendering never posts records or accounting entries.
Use normal reviewed posting separately when authorized. New saves to posted
records are rejected; download the preserved attachment for a historical copy.

After deploying both services, refresh the testing plugin's tool catalog at the
configured `/qledger` endpoint. Test QAuth login/unit selection, guidance/schema,
an image-bearing preview, saving/retrying and PDF download in ChatGPT. Automated
tests cover mocked upstream APIs; live credentials and ChatGPT's binary-file
presentation still need that acceptance check.
