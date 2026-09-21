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


## CashflowPot

CashflowPot tools use the authenticated Quollnet MCP token only to obtain a
normal CashflowPot app token from QAuth. q_flow remains authoritative for Unit
permissions, validation, calculations, persistence, and returned KPIs.

Required environment values are documented in `.env.example`, including
`CASHFLOWPOT_APP_ID` and `QFLOW_BASE_URL`.

Initial tools:

- `list_cashflow_projects`
- `create_cashflow`


## Quollnet qTools V2

qTools V2 uses qApp as the authoritative backend for tool metadata, package
storage, validation, lifecycle, public rendering, and article embedding.

The MCP gateway exposes the qTool authoring workflow through:

- `get_qtool_generation_spec`
- `list_qtools`
- `get_qtool`
- `create_qtool`
- `update_qtool_metadata`
- `list_qtool_files`
- `get_qtool_file`
- `write_qtool_file`
- `delete_qtool_file`
- `save_qtool`
- `publish_qtool`
- `disable_qtool`
- `set_qtool_indexing`

The Quollnet MCP application's QAuth `mcp_oauth.role_scopes` configuration must
grant the following scopes to the appropriate roles:

- `qtools:read`
- `qtools:create`
- `qtools:edit`
- `qtools:publish`

A creator/editor role should normally receive `qtools:read`,
`qtools:create`, and `qtools:edit`. The role used for qApp administration
must also receive `qtools:publish`; qApp independently verifies the
authenticated token's `admin` app role before publish, disable, or indexing
operations.

The existing `quollnet:access` MCP scope remains required by the MCP server.
