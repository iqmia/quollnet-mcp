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
