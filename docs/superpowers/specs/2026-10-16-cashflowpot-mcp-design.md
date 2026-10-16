# CashflowPot MCP Design

Date: 16 October 2026
Status: Design approved in conversation; implementation not started

## 1. Purpose

Add a dedicated CashflowPot MCP endpoint to the existing `iqmia/quollnet-mcp` service without changing the behavior of the existing `/mcp` endpoint.

The dedicated MCP must expose the complete CashflowPot modeling surface needed by an AI client: projects, cashflow scenarios, activities, financing facilities, calculated results, portable scenario import/export, and Excel export.

CashflowPot business logic remains in `q_flow`. The MCP is an authenticated adapter and must not duplicate the cash-flow calculation model.

## 2. Deployment architecture

Keep one repository and one running MCP service on `mcp.quollnet.com`.

```text
mcp.quollnet.com
├── /mcp          existing Quollnet MCP; behavior unchanged
└── /cashflowpot  dedicated CashflowPot MCP
```

Both MCP applications share common server infrastructure, QAuth integration, token verification, HTTP clients, logging, health checks, and deployment.

The CashflowPot MCP calls the production CashflowPot backend at `cashflowpot.com/api` (or the configured `QFLOW_BASE_URL`).

```text
ChatGPT / MCP client
        |
        | OAuth + PKCE
        v
      QAuth
        |
        | MCP access token
        | aud = https://mcp.quollnet.com/cashflowpot
        v
CashflowPot MCP (/cashflowpot)
        |
        | exchange-token
        | target_app_id = CASHFLOWPOT_APP_ID
        | unit_id = project id when required
        v
      QAuth
        |
        | normal CashflowPot app/unit token
        v
      q_flow
        |
        v
CashflowPot persistence + authoritative calculations
```

## 3. Authentication and authorization

QAuth remains the single OAuth authority for both MCP endpoints.

The QAuth MCP gateway application must include `https://mcp.quollnet.com/cashflowpot` as an allowed MCP resource. Tokens issued for this endpoint must use that resource as the JWT audience.

CashflowPot remains a target application with `allow_quollnet_mcp_exchange = true`. It does not need its own independent MCP OAuth implementation.

The shared QAuth client exchanges the MCP access token for:

- a normal CashflowPot application token for project discovery and project creation; or
- a normal CashflowPot unit token when an operation targets an existing project.

There is no additional MCP permission model. All CashflowPot MCP tools are exposed to an authenticated CashflowPot user. `q_flow` and QAuth remain authoritative for application membership, project/unit membership, validation, and any existing permission checks.

The server must never invent roles, permissions, ownership, project IDs, cashflow IDs, activity IDs, or calculated values.

## 4. Server separation inside the shared service

The new endpoint must be logically isolated even though it runs in the same process as the existing Quollnet MCP.

Recommended package boundary:

```text
quollnet_mcp/
├── core/                  shared infrastructure
│   ├── auth.py
│   ├── qauth_client.py
│   ├── token_exchange.py
│   └── config.py
├── quollnet/              existing general MCP surface
│   └── ...
└── cashflowpot/
    ├── server.py
    ├── models.py
    ├── tools/
    │   ├── projects.py
    │   ├── cashflows.py
    │   ├── activities.py
    │   ├── facilities.py
    │   └── exports.py
    └── qflow_client.py
```

The exact file move/refactor may follow the current repository layout, but CashflowPot-specific tools must not be registered on `/mcp` as part of this work. Existing `/mcp` behavior is intentionally left unchanged.

## 5. Design principle: MCP adapts, q_flow owns the model

The MCP tool surface should match how a user thinks about CashflowPot rather than mechanically mirror every HTTP endpoint.

The MCP may expose convenient object-level operations, but every mutation must ultimately go through `q_flow` so that the existing backend performs validation, normalization, calculation, persistence, and recalculation.

The MCP must not independently calculate:

- Activity curves;
- client inflow;
- project outflow;
- net cash flow;
- financing draws or repayments;
- interest or fees;
- facility outstanding balances;
- funding requirement;
- cash position; or
- summary KPIs.

Returned calculated values always come from `q_flow`.

## 6. MCP tool surface

The dedicated `/cashflowpot` MCP exposes the following tool names and capabilities.

### 6.1 Projects

Read:

- `list_cashflow_projects`
- `get_cashflow_project`

Mutate:

- `create_cashflow_project`
- `update_cashflow_project`
- `delete_cashflow_project`
- `restore_cashflow_project`
- `hard_delete_cashflow_project`

Project creation follows the current q_flow behavior, including creation of the QAuth Unit and the initial Base Cashflow.

### 6.2 Cashflow scenarios

Read:

- `get_cashflow`
- `get_cashflow_results`

Mutate:

- `create_cashflow`
- `update_cashflow`
- `delete_cashflow`
- `restore_cashflow`
- `hard_delete_cashflow`

Portable scenario operations:

- `export_cashflow_json`
- `import_cashflow_json`

`export_cashflow_json` returns the versioned portable `cashflowpot.cashflow` input model rather than a raw API/database serialization.

`import_cashflow_json` submits that portable model to the authoritative q_flow import path.

`get_cashflow_results` returns a calculation-focused payload containing the authoritative project cashflow series, financing rows, cash position, and summary/KPI values without requiring the client to infer them from source inputs.

### 6.3 Activities

Read:

- `get_activity`
- `get_activity_types`
- `list_deleted_activities`

Mutate:

- `create_activity`
- `update_activity`
- `delete_activity`
- `restore_activity`
- `restore_activities`
- `hard_delete_activity`

The tool schema must support both current Activity modes:

- `work`; and
- `scheduled_cost`.

For Work, the MCP schema must support `s_curve`, `linear`, and `manual` distributions and all currently active commercial/timing inputs.

For Scheduled Cost, the schema must support the dense local `cost_schedule_json` plus `start`, with q_flow deriving cost/duration according to the existing model.

### 6.4 Financing facilities

Read:

- `list_financing_facility_presets`
- `list_financing_facilities`
- `get_financing_facility`

Mutate:

- `add_financing_facility`
- `update_financing_facility`
- `delete_financing_facility`
- `set_financing_facility_order`

Facilities remain embedded source data inside the owning Cashflow's `financing_facilities` JSON array. They do not become independent database entities.

The object-level MCP tools are convenience operations only. q_flow provides atomic facility mutation endpoints that update the embedded list, validate the complete facility set, recalculate the cashflow, and return the updated authoritative snapshot.

Facility IDs remain source-level identifiers used to address a facility inside the embedded array. q_flow ensures a stable ID exists for a newly added facility if one is not supplied.

`set_financing_facility_order` updates the saved facility order and the corresponding sweep priority values used by the financing engine.

### 6.5 Excel export

Required tool:

- `export_cashflow_excel`

This tool requests a backend-generated `.xlsx` report from q_flow. Excel generation does not live in the MCP service.

## 7. Financing facility persistence and portability

Financing facilities intentionally remain part of the Cashflow aggregate because a scenario must remain portable and shareable as one JSON document.

```text
Cashflow portable scenario
├── commercial assumptions
├── inflow settings
├── activities
└── financing_facilities
```

Exporting a portable cashflow must preserve all facility source definitions. Importing the scenario on another CashflowPot account/project must recreate the same modeling inputs and let q_flow recalculate all derived outputs.

Calculated facility rows such as draw, repayment, interest, fees, outstanding, and available limit are not portable inputs.

## 8. q_flow API additions

The MCP reuses existing q_flow routes wherever they already express the required operation correctly.

New backend routes/services are required in three areas.

### 8.1 Atomic facility operations

Add q_flow operations for addressing a single facility within `cashflow.financing_facilities` without turning facilities into database rows.

```text
POST   /cashflow/<cashflow_id>/facilities
PUT    /cashflow/<cashflow_id>/facilities/<facility_id>
DELETE /cashflow/<cashflow_id>/facilities/<facility_id>
PUT    /cashflow/<cashflow_id>/facilities/order
```

Each mutation must:

1. load the active cashflow;
2. enforce normal CashflowPot authorization;
3. mutate only the targeted facility definition or ordering;
4. validate the complete facility list using the existing financing validator;
5. recalculate the cashflow snapshot through the normal calculation engine;
6. commit atomically; and
7. return the updated authoritative cashflow snapshot.

### 8.2 Portable JSON export

Add a q_flow export route so the portable schema is owned by the backend rather than reconstructed independently in the MCP.

```text
GET /cashflow/<cashflow_id>/export
```

It returns:

```json
{
  "format": "cashflowpot.cashflow",
  "version": 1,
  "cashflow": {}
}
```

The response contains only portable source inputs defined by the canonical CashflowPot JSON format. It excludes server-owned IDs/ownership metadata and calculated output except for source-level facility IDs used inside the embedded facility list.

### 8.3 Backend Excel export

Add a backend Excel report generator plus a signed-download-link endpoint.

The authenticated creation endpoint is:

```text
POST /cashflow/<cashflow_id>/excel-export
```

It returns metadata in this shape:

```json
{
  "filename": "<safe-cashflow-name>.xlsx",
  "download_url": "https://cashflowpot.com/api/exports/cashflow/<signed-token>.xlsx",
  "expires_at": "<ISO-8601 timestamp>"
}
```

The signed download endpoint is:

```text
GET /exports/cashflow/<signed-token>.xlsx
```

The backend verifies the signature/expiry, resolves the authorized cashflow encoded by the token, generates the workbook on demand, and returns the XLSX bytes. The signed URL is possession-based and replayable only until expiry; no temporary file persistence is required in the first implementation.

The Excel generator consumes the authoritative calculated cashflow snapshot and must not reproduce the financial model with alternative formulas.

## 9. Excel parity requirement

The current Flutter Excel exporter is the reference implementation.

The Python backend report must reproduce the current approved workbook as exactly as practicable because its geometry and print setup were deliberately tuned for good A4 and A3 output/PDF printing.

Parity includes, where present in the Flutter exporter:

- workbook/sheet structure;
- sheet names;
- row and column positions;
- merged cells;
- widths and heights;
- fonts and number formats;
- fills, borders, and alignment;
- formulas used for report aggregation;
- charts and chart series;
- project, facility, and cash-position sections;
- Key Metrics;
- one-decimal cash presentation;
- print areas;
- orientation;
- paper size;
- fit-to-page / scaling behavior;
- margins;
- repeating rows/columns if used;
- A4/A3 print geometry; and
- any targeted OOXML polish required for visual parity.

The backend-calculated flow arrays and KPIs remain authoritative. Spreadsheet formulas may aggregate or present those values, but the workbook must not become a second financing/calculation engine.

### 9.1 Python workbook stack

Implementation begins with a parity audit of the current Flutter `ExcelExporterV3`/OOXML pipeline.

Use `XlsxWriter` as the Python workbook library. It provides the formatting, formulas, charts, print areas, page setup, margins, and workbook generation needed for the report. Where exact parity requires an OOXML detail that XlsxWriter does not expose, apply narrowly scoped OOXML post-processing after workbook generation, mirroring the existing Flutter approach.

Do not introduce a second competing Python workbook library for the same report pipeline.

## 10. XLSX delivery

Do not put the entire XLSX byte stream into the normal MCP tool response by default.

MCP supports binary resources and resource links, but embedding a workbook as base64 increases payload size and is unnecessarily expensive for normal downloads.

The flow is:

```text
export_cashflow_excel tool
        |
        | authenticated request
        v
POST q_flow /cashflow/<id>/excel-export
        |
        | filename + short-lived signed HTTPS URL
        v
MCP returns filename + URL (+ ResourceLink when supported)
        |
        v
client/browser downloads .xlsx directly from cashflowpot.com
```

The signed URL must:

- be scoped to one cashflow export;
- expire after a short configurable interval;
- be unguessable/tamper-evident;
- not expose the QAuth/MCP bearer token in the URL;
- return MIME type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`;
- set `Content-Disposition: attachment` with a safe filename; and
- generate the workbook on demand in the first implementation.

For clients that support MCP resources well, the MCP additionally returns a `ResourceLink` when practical, but the signed HTTPS URL remains the compatibility path for a user-visible workbook download.

## 11. Destructive operations

Because CashflowPot is treated as a single-user application and the user requested the full action surface, the dedicated MCP exposes delete, restore, and hard-delete operations instead of maintaining an MCP-side allowlist.

Destructive tools use standard MCP destructive annotations/hints where supported so clients can present them appropriately. The server does not create a second confirmation/permission system.

q_flow remains authoritative for whether the authenticated user may perform the operation.

## 12. Error handling

The MCP normalizes transport failures into concise tool errors while preserving useful backend validation messages.

Examples:

- authentication missing/expired;
- QAuth token exchange denied;
- project/unit access denied;
- object not found;
- invalid cashflow/activity/facility input;
- unsupported portable format/version;
- calculation failure;
- Excel generation failure; and
- download-link generation failure.

The MCP must not convert backend validation errors into silent defaults.

Mutations that q_flow defines as transactional must remain transactional through the MCP.

## 13. Testing strategy

### 13.1 quollnet-mcp

Add focused tests for:

- `/cashflowpot` server registration independent from `/mcp`;
- CashflowPot resource audience validation;
- shared QAuth token exchange;
- app-token versus unit-token exchange;
- every tool's request mapping;
- facility convenience tool mapping;
- portable JSON import/export;
- destructive tool annotations where supported;
- Excel export metadata/download-link response; and
- q_flow/QAuth error propagation.

Existing `/mcp` tests must continue to pass unchanged.

### 13.2 q_flow

Add tests for:

- atomic facility add/update/delete/order operations;
- facility ID creation/preservation;
- full-list facility validation after mutation;
- recalculation after facility mutation;
- backend portable JSON export;
- portable JSON round-trip remaining complete;
- Excel workbook generation from an authoritative snapshot;
- sheet/row/column geometry;
- formulas and numerical values;
- facility section layout;
- charts;
- print area/page setup/margins;
- A4/A3 settings;
- XLSX MIME type and filename headers;
- signed-link expiry/tamper rejection; and
- authorization of export-link creation.

### 13.3 Excel parity fixtures

Use representative scenarios that exercise:

- Work Activities;
- Manual Work;
- Scheduled Cost;
- Independent inflow;
- Activity-linked inflow;
- no financing facilities;
- several different facility types;
- multiple facility colors/rows;
- long financial horizons; and
- non-zero debt at the horizon.

Compare the Python workbook against the approved Flutter exporter at the semantic and OOXML/layout levels rather than relying only on opening the file manually.

## 14. Compatibility and rollout

This work must not change the existing `/mcp` tool surface or behavior.

Rollout order:

1. add q_flow portable export, facility APIs, and backend Excel exporter;
2. verify q_flow independently;
3. add QAuth CashflowPot MCP resource configuration;
4. add the dedicated `/cashflowpot` MCP server and full tool surface;
5. deploy/restart the existing MCP service;
6. connect the dedicated CashflowPot MCP endpoint in a client;
7. run end-to-end CRUD, portable JSON, calculation, and Excel download tests.

The current CashflowPot tools already present on `/mcp` are left in place for compatibility unless a separate future change explicitly removes them.

## 15. Success criteria

The design is complete when an authenticated user can connect directly to `https://mcp.quollnet.com/cashflowpot` and, through MCP tools alone:

- discover and manage CashflowPot projects;
- create, inspect, edit, delete, restore, import, and export cashflow scenarios;
- create and manage all current Activity types/modes;
- create and manage financing facilities while facilities remain embedded in the scenario;
- receive q_flow's authoritative calculated results and KPIs;
- share a complete portable CashflowPot JSON scenario; and
- download an Excel workbook that matches the approved Flutter report and A4/A3 print behavior.

No CashflowPot financial calculation is independently implemented in the MCP service.