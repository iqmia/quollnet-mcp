# Quollnet MCP

Minimal standalone MCP server using the official `mcp==2.0.0` SDK.

## Install

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

The MCP Streamable HTTP endpoint is `http://127.0.0.1:8000/mcp`.
The health check is `http://127.0.0.1:8000/health`.

Configuration is environment-based. Copy `.env.example` to `.env` and export
the values in your shell before starting Uvicorn.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Authentication and authorization

The Quollnet MCP OAuth token establishes the connected QAuth identity. For a
target Quollnet application, the MCP exchanges that identity through QAuth for
the same normal application or user/unit token that the target application
already understands.

The MCP does not maintain a parallel application-permission model. Target
applications remain authoritative for their own roles, permissions, validation,
and persistence. For example, qApp interprets its normal `app_roles`, while
unit-based applications continue to interpret their normal unit roles and
permissions.

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

CashflowPot tools use the authenticated Quollnet MCP token only to obtain a
normal CashflowPot app token from QAuth. q_flow remains authoritative for Unit
permissions, validation, calculations, persistence, and returned KPIs.

Required environment values are documented in `.env.example`, including
`CASHFLOWPOT_APP_ID` and `QFLOW_BASE_URL`.

Initial tools:

- `list_cashflow_projects`
- `create_cashflow`
