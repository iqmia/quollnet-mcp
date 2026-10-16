# CashflowPot MCP Implementation Plan

> **REQUIRED SUB-SKILL:** Use `superpowers:test-driven-development` for every implementation task below. Before claiming any task or the whole project complete, use `superpowers:verification-before-completion`.

**Goal:** Add a dedicated `https://mcp.quollnet.com/cashflowpot` MCP resource to the existing `iqmia/quollnet-mcp` service, exposing the complete CashflowPot user-facing surface while keeping `q_flow` authoritative for validation, persistence, calculation, portable JSON, and Excel generation.

**Architecture:** `q_flow` gains the missing backend capabilities first: canonical portable JSON export, atomic embedded-facility mutation routes, a Python/XlsxWriter report that matches the approved Flutter workbook, and stateless signed Excel-download URLs that generate the workbook in memory. `quollnet-mcp` then adds a second MCP server mounted at `/cashflowpot`, sharing the existing QAuth token verifier/exchange clients and q_flow client infrastructure while leaving the current `/mcp` endpoint unchanged. QAuth itself needs only deployment configuration: add the CashflowPot MCP resource URI to the existing QAuth MCP gateway application.

**Tech Stack:** Flask 3 / SQLAlchemy / PyJWT / XlsxWriter in `iqmia/q_flow`; MCP Python SDK 2.0 / Starlette / httpx / PyJWT in `iqmia/quollnet-mcp`; pytest for q_flow; unittest for quollnet-mcp.

**Approved design:** `docs/superpowers/specs/2026-10-16-cashflowpot-mcp-design.md`

## Non-negotiable constraints

- Do not remove, rename, or change behavior of existing `/mcp` tools in this work.
- Keep one `quollnet-mcp` repository and one running MCP service.
- QAuth remains the single OAuth authority; do not create a CashflowPot-specific login or permission system.
- `q_flow` remains authoritative for all financial calculations, validation, persistence, unit permissions, and returned KPIs.
- Financing facilities remain embedded in `Cashflow.financing_facilities`; do not create a facility database table.
- Portable JSON remains `format = cashflowpot.cashflow`, `version = 1` and stores source inputs rather than calculated output.
- The backend Excel report must match the approved Flutter Excel V3 report and print geometry as closely as practicable before it is considered complete.
- Use XlsxWriter as the single Python workbook library; use narrowly scoped OOXML post-processing only where parity requires it.
- Never persist generated XLSX files. Generate into memory when the signed URL is opened and release the bytes after the response.
- No database migration is required for this feature.

---

## Task 1: Make portable cashflow JSON a backend-owned read/write contract

**Repository:** `iqmia/q_flow`

**Files:**
- Create: `q_flow/services/portable_cashflow.py`
- Modify: `q_flow/routes/cashflows.py`
- Modify: `documentation/reference/cashflow_json_format.md`
- Modify: `documentation/technical.md`
- Create: `tests/test_cashflow_export.py`
- Modify: `tests/test_cashflow_import.py`

**Interfaces:**

```python
PORTABLE_FORMAT = "cashflowpot.cashflow"
PORTABLE_VERSION = 1
CASHFLOW_SOURCE_FIELDS: tuple[str, ...]
ACTIVITY_SOURCE_FIELDS: tuple[str, ...]


def build_portable_cashflow(cashflow: Cashflow) -> dict[str, Any]:
    """Return version-1 portable source inputs for one active cashflow."""
```

The existing import route and the new export route must consume the same source-field definitions so import/export cannot silently drift.

- [ ] **Step 1: Write failing portable-export tests.** Add `tests/test_cashflow_export.py` covering `GET /cashflow/<id>/export`: the response has `format`, `version`, all current cashflow source fields, all current Activity source fields, embedded `financing_facilities`, and no calculated arrays, timestamps, ownership, deletion state, cashflow ID, Activity ID, or cached `cash_flow_json`. Preserve source-level facility IDs when present.
- [ ] **Step 2: Add a round-trip regression.** Extend `tests/test_cashflow_import.py` so export -> import recreates the same source assumptions, Work/Manual/Scheduled Cost Activity inputs, inflow settings, and facility definitions while recalculating server-owned results.
- [ ] **Step 3: Run the focused tests and confirm RED.** `pytest tests/test_cashflow_export.py tests/test_cashflow_import.py -q`
- [ ] **Step 4: Implement the shared portable model.** Move the canonical format/version and allowed input field sets out of `routes/cashflows.py` into `q_flow/services/portable_cashflow.py`; implement `build_portable_cashflow()` from ORM source fields only.
- [ ] **Step 5: Add the authorized export route.** In `q_flow/routes/cashflows.py`, add `GET /cashflow/<cashflow_id>/export`; load the active cashflow, require `VIEW_CASHFLOW`, return `build_portable_cashflow(cashflow)`. Update the existing import path to reuse the shared constants/field sets.
- [ ] **Step 6: Run focused tests and confirm GREEN.** `pytest tests/test_cashflow_export.py tests/test_cashflow_import.py -q`
- [ ] **Step 7: Update the canonical docs.** Document that q_flow now owns both import and export serialization and that facility source IDs are allowed while calculated facility rows remain excluded.
- [ ] **Step 8: Commit q_flow.** `git add q_flow/services/portable_cashflow.py q_flow/routes/cashflows.py tests/test_cashflow_export.py tests/test_cashflow_import.py documentation/reference/cashflow_json_format.md documentation/technical.md && git commit -m "feat: add canonical cashflow portable export"`

---

## Task 2: Add atomic APIs for embedded financing facilities

**Repository:** `iqmia/q_flow`

**Files:**
- Create: `q_flow/services/cashflow_facilities.py`
- Modify: `q_flow/routes/cashflows.py`
- Modify: `q_flow/financing.py`
- Create: `tests/test_cashflow_facility_routes.py`
- Modify: `tests/test_financing_engine.py` only if validator-level coverage belongs there

**Interfaces:**

```python
def add_facility(facilities: object, data: Mapping[str, Any]) -> list[dict[str, Any]]: ...
def update_facility(facilities: object, facility_id: str, data: Mapping[str, Any]) -> list[dict[str, Any]]: ...
def delete_facility(facilities: object, facility_id: str) -> list[dict[str, Any]]: ...
def set_facility_order(facilities: object, facility_ids: Sequence[str]) -> list[dict[str, Any]]: ...
def get_facility(facilities: object, facility_id: str) -> dict[str, Any]: ...
```

Backend routes:

```text
GET    /cashflow/<cashflow_id>/facilities
GET    /cashflow/<cashflow_id>/facilities/<facility_id>
POST   /cashflow/<cashflow_id>/facilities
PUT    /cashflow/<cashflow_id>/facilities/<facility_id>
DELETE /cashflow/<cashflow_id>/facilities/<facility_id>
PUT    /cashflow/<cashflow_id>/facilities/order
```

- [ ] **Step 1: Write failing route/service tests.** Cover list/get, generated stable ID on add, caller-supplied unique ID preservation, update preserving the addressed ID, delete of only the addressed facility, and not-found behavior.
- [ ] **Step 2: Add validation/atomicity tests.** Cover duplicate facility IDs, duplicate facility names, invalid method-specific fields, attempted ID mutation on update, and rollback when the complete post-mutation facility set is invalid. Assert the database retains the pre-request JSON after failure.
- [ ] **Step 3: Add ordering tests.** `PUT .../facilities/order` must require every current facility ID exactly once, reorder the embedded list, and rewrite `sweep_priority` sequentially according to saved order.
- [ ] **Step 4: Add recalculation regression.** After add/update/delete/order, assert the returned cashflow snapshot contains newly recalculated facility rows/summary values rather than stale values.
- [ ] **Step 5: Run focused tests and confirm RED.** `pytest tests/test_cashflow_facility_routes.py tests/test_financing_engine.py -q`
- [ ] **Step 6: Implement pure facility-list helpers.** Always copy the incoming list/dicts before mutation; use `gen_id()` when a new facility has no ID; do not allow updates to replace the target ID; return a new list so SQLAlchemy JSON dirty tracking is reliable.
- [ ] **Step 7: Harden `validate_financing_facilities`.** Require non-empty unique facility IDs for persisted/MCP-addressable facility lists without changing the existing calculation semantics. Normalize only what is necessary for stable addressing; do not turn facilities into ORM objects.
- [ ] **Step 8: Add read/mutation routes.** Use `_active_cashflow`, normal `VIEW_CASHFLOW`/`EDIT_CASHFLOW` checks, `_validate_cashflow`, `db.session.flush()`, `cashflow.as_dict_with_activities()`, and one commit. Roll back the entire mutation on any exception.
- [ ] **Step 9: Run focused tests and confirm GREEN.** `pytest tests/test_cashflow_facility_routes.py tests/test_financing_engine.py tests/test_financing_summary.py -q`
- [ ] **Step 10: Commit q_flow.** `git add q_flow/services/cashflow_facilities.py q_flow/routes/cashflows.py q_flow/financing.py tests/test_cashflow_facility_routes.py tests/test_financing_engine.py && git commit -m "feat: add atomic cashflow facility operations"`

---

## Task 3: Reproduce the approved Flutter Excel report in Python

**Repository:** `iqmia/q_flow`

**Reference repository:** `iqmia/cashflowpot`

**Reference files (read-only for this task):**
- `lib/src/utils/export_excel_v2.dart`
- `lib/src/utils/export_excel_v3.dart`
- `lib/src/utils/excel_v2_styles.dart`
- `lib/src/utils/excel_v2_formulas.dart`
- `lib/src/utils/excel_v2_ooxml.dart`
- `lib/src/utils/excel_v3_io.dart`
- `test/excel_export_v2_test.dart`
- `test/excel_export_v2_final_polish_test.dart`
- `test/excel_export_full_cashflow_test.dart`

**Files:**
- Modify: `requirements.txt`
- Create: `q_flow/reports/__init__.py`
- Create: `q_flow/reports/cashflow_excel.py`
- Create: `q_flow/reports/cashflow_excel_ooxml.py`
- Create binary asset: `q_flow/static/reports/qflow_logo.png` copied byte-for-byte from `iqmia/cashflowpot:assets/icon/qflow_logo.png`
- Create: `tests/test_cashflow_excel.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class FacilityLayout:
    draw_row: int
    repayment_row: int
    cost_row: int
    outstanding_row: int


@dataclass(frozen=True)
class CashflowLayout:
    ...


def period_count_for(snapshot: Mapping[str, Any]) -> int: ...
def layout_for(snapshot: Mapping[str, Any]) -> CashflowLayout: ...
def build_cashflow_excel(*, project_name: str, snapshot: Mapping[str, Any]) -> bytes: ...
```

The generator receives `Cashflow.as_dict_with_activities()` output. It must not call or recreate the financing engine.

- [ ] **Step 1: Port the approved Flutter assertions before implementation.** Build a Python fixture equivalent to the existing Harbour Tower/full-financing test and assert: single `Cash Flow` sheet; H as first period column; group row 37; activity header row 38; two rows/activity; Project Cashflow / Facilities / Cash Position layout; four rows/facility; merged/rotated facility name; four cycling pastel fills; one-decimal money formats; Cash after debt settlement KPI; period groups of four; and extended financial horizon.
- [ ] **Step 2: Add OOXML parity assertions.** Inspect the XLSX zip with stdlib `zipfile`/XML. Assert hidden gridlines; `paperSize="9"`; landscape orientation; final margins `0.19685` left/right/top/bottom and `0.15` header/footer; formula recalculation; chart ranges; chart colors `5F8F73`, `C7775E`, `4F6D86`; approved chart positions/extents; logo relationship and dimensions. Do not add openpyxl merely for testing.
- [ ] **Step 3: Add horizon/report-input tests.** Cover no facilities, five facilities (pastel cycling), Manual Work, Scheduled Cost, Activity-linked inflow, Independent inflow, long facility horizon beyond Work duration, and debt remaining at horizon.
- [ ] **Step 4: Run the tests and confirm RED.** `pytest tests/test_cashflow_excel.py -q`
- [ ] **Step 5: Add XlsxWriter.** Pin `XlsxWriter==3.2.9` in `requirements.txt`; do not add a second workbook library.
- [ ] **Step 6: Copy the exact CashflowPot logo asset.** Store it under `q_flow/static/reports/qflow_logo.png`; no runtime dependency on the Flutter repository or `/app` deployment.
- [ ] **Step 7: Implement workbook geometry/styles/formulas.** Translate the current V2/V3 row/column layout, labels, assumptions, KPI blocks, Activity schedule, Project Cashflow, Facilities, Cash Position, reconciliation/notes, totals and closing-balance formulas using backend-provided arrays and summary values.
- [ ] **Step 8: Implement charts and print setup with XlsxWriter first.** Match current chart series, labels, colors, page layout, margins, widths/heights, merged cells, and A4 landscape geometry. Use workbook formulas for transparent report aggregation only; do not independently calculate facility behavior.
- [ ] **Step 9: Add narrow OOXML finalization only for mismatches.** Put any unavoidable direct XML patch in `cashflow_excel_ooxml.py`, document exactly which XlsxWriter limitation it addresses, and keep transforms deterministic/idempotent.
- [ ] **Step 10: Run Excel parity tests and confirm GREEN.** `pytest tests/test_cashflow_excel.py -q`
- [ ] **Step 11: Manually compare one Python workbook with the Flutter exporter.** Open/print-preview both the representative A4/A3 report and verify visual parity; record any intentional difference in the test/doc comments before proceeding.
- [ ] **Step 12: Commit q_flow.** `git add requirements.txt q_flow/reports q_flow/static/reports/qflow_logo.png tests/test_cashflow_excel.py && git commit -m "feat: generate CashflowPot Excel reports on backend"`

---

## Task 4: Add stateless signed Excel download URLs with zero XLSX storage

**Repository:** `iqmia/q_flow`

**Files:**
- Create: `q_flow/services/excel_export_tokens.py`
- Create: `q_flow/routes/exports.py`
- Modify: `q_flow/config.py`
- Modify: `q_flow/__init__.py`
- Create: `tests/test_cashflow_excel_download.py`
- Modify: `tests/test_config_runtime.py`
- Modify: `documentation/technical.md`
- Modify: `documentation/deployment.md`

**Configuration:**

```text
PUBLIC_API_BASE_URL=https://cashflowpot.com/api
EXCEL_EXPORT_TOKEN_TTL_SECONDS=600
```

**Signed-token contract:** use existing PyJWT with `SECRET_KEY`, HS256, and dedicated claims so this token cannot be confused with QAuth/user tokens.

```text
iss = cashflowpot
 aud = cashflowpot-excel-export
purpose = cashflow_excel
cashflow_id
unit_id
project_name
iat
exp
```

**Interfaces:**

```python
@dataclass(frozen=True)
class ExcelExportClaims:
    cashflow_id: str
    unit_id: str
    project_name: str
    expires_at: datetime


def create_excel_export_token(..., ttl_seconds: int, now: datetime | None = None) -> tuple[str, datetime]: ...
def decode_excel_export_token(..., now: datetime | None = None) -> ExcelExportClaims: ...
```

Routes:

```text
POST /cashflow/<cashflow_id>/excel-export          # normal Bearer auth required
GET  /exports/cashflow/<signed-token>.xlsx         # signed-link possession only
```

- [ ] **Step 1: Write token tests first.** Cover valid decode, tampered token rejection, expired token rejection, wrong audience/purpose rejection, and deterministic expiry with injected `now`.
- [ ] **Step 2: Write creation-route tests.** Require normal CashflowPot auth and `VIEW_CASHFLOW`; resolve the cashflow's current QAuth project name; assert metadata shape `{filename, download_url, expires_at}` and URL prefix from `PUBLIC_API_BASE_URL` rather than Flask's internal proxy URL.
- [ ] **Step 3: Write download-route tests.** No Authorization header is required. Verify token, active cashflow existence, and exact `unit_id` match; call the report builder with the current authoritative snapshot; return XLSX MIME type and safe `Content-Disposition` filename.
- [ ] **Step 4: Add the no-storage regression.** Patch/inspect report generation and the configured storage directory to prove the download path returns bytes without creating an `.xlsx` file on disk. Two downloads during the TTL may regenerate the workbook; they must not create persistent artifacts.
- [ ] **Step 5: Run focused tests and confirm RED.** `pytest tests/test_cashflow_excel_download.py tests/test_config_runtime.py -q`
- [ ] **Step 6: Implement export-token service and config.** Keep a 600-second default TTL; make the public API base URL explicit because Apache strips `/api` before Flask sees the request.
- [ ] **Step 7: Implement `exports` blueprint.** The POST route creates only a signed URL. The GET route generates the workbook in memory (`bytes`/`BytesIO`) and returns it; no temp directory, export table, cleanup job, or stored artifact.
- [ ] **Step 8: Register the blueprint and run focused tests GREEN.** `pytest tests/test_cashflow_excel_download.py tests/test_cashflow_excel.py tests/test_config_runtime.py -q`
- [ ] **Step 9: Update deployment docs.** Document the two new config values and explicitly state that generated workbooks are stateless/in-memory.
- [ ] **Step 10: Commit q_flow.** `git add q_flow/services/excel_export_tokens.py q_flow/routes/exports.py q_flow/config.py q_flow/__init__.py tests/test_cashflow_excel_download.py tests/test_config_runtime.py documentation/technical.md documentation/deployment.md && git commit -m "feat: add stateless Excel export links"`

---

## Task 5: Add a second MCP resource at `/cashflowpot` without touching `/mcp`

**Repository:** `iqmia/quollnet-mcp`

**Files:**
- Modify: `quollnet_mcp/config.py`
- Modify: `.env.example`
- Create: `quollnet_mcp/cashflowpot/__init__.py`
- Create: `quollnet_mcp/cashflowpot/instructions.py`
- Create: `quollnet_mcp/cashflowpot/server.py`
- Modify: `app.py`
- Create: `tests/test_cashflowpot_server.py`
- Modify: `tests/test_app.py`

**Configuration:**

```text
CASHFLOWPOT_MCP_RESOURCE_URI=https://mcp.quollnet.com/cashflowpot
```

**Server interface:**

```python
def build_cashflowpot_server(settings: Settings) -> MCPServer: ...
```

- [ ] **Step 1: Write resource-audience isolation tests.** Generate test RSA JWTs and prove the existing verifier/resource accepts only the `/mcp` audience while the CashflowPot verifier accepts only `https://mcp.quollnet.com/cashflowpot`. A token for one resource must be rejected by the other.
- [ ] **Step 2: Write mount/lifecycle tests.** Assert the dedicated application is reachable at `/cashflowpot` (not `/cashflowpot/mcp`), `/mcp` is still reachable exactly as before, and both MCP session managers are entered/exited in the single Starlette lifespan while qApp/QAuth/qFlow clients remain shared.
- [ ] **Step 3: Write configuration tests.** Existing `MCP_RESOURCE_URI` remains unchanged; new `CASHFLOWPOT_MCP_RESOURCE_URI` defaults independently to the dedicated production URL.
- [ ] **Step 4: Run focused tests and confirm RED.** `python -m unittest tests.test_cashflowpot_server tests.test_app -v`
- [ ] **Step 5: Implement the dedicated server.** Instantiate a second `MCPServer` with the existing `QAuthTokenVerifier`, same issuer/app/public key, `resource_uri=settings.cashflowpot_mcp_resource_uri`, and CashflowPot-specific instructions. Do not register general Quollnet/QArticle/qTool tools on it.
- [ ] **Step 6: Mount safely.** Build the dedicated Streamable HTTP app with `streamable_http_path="/"`; mount `Mount("/cashflowpot", ...)` before the existing catch-all mount. Keep the existing central MCP construction and tool registrations unchanged.
- [ ] **Step 7: Share process dependencies, not server state.** In the lifespan, enter `qapp_client`, `qauth_client`, `qflow_client`, then both MCP session managers (use `AsyncExitStack` if cleaner). Do not create a second QAuth/qFlow client pool.
- [ ] **Step 8: Run focused tests GREEN.** `python -m unittest tests.test_cashflowpot_server tests.test_app -v`
- [ ] **Step 9: Commit quollnet-mcp.** `git add quollnet_mcp/config.py .env.example quollnet_mcp/cashflowpot app.py tests/test_cashflowpot_server.py tests/test_app.py && git commit -m "feat: mount dedicated CashflowPot MCP resource"`

---

## Task 6: Expand the shared q_flow HTTP client to the complete backend surface

**Repository:** `iqmia/quollnet-mcp`

**Files:**
- Modify: `quollnet_mcp/services/qflow_client.py`
- Modify: `tests/test_backend_clients.py`

**Required client capability groups:**

```text
Projects: list/get/create/update/delete/restore/hard-delete
Cashflows: get/create/update/delete/restore/hard-delete/import/export
Results: get authoritative cashflow snapshot/results
Activities: types/get/create/update/delete/restore/restore-many/hard-delete/deleted-list
Facilities: presets/list/get/add/update/delete/order
Exports: request Excel export metadata
```

- [ ] **Step 1: Write route-mapping tests first.** For every new client method, use `httpx.MockTransport` to assert HTTP method, quoted path parameters, Authorization header, query string/body, and response/error mapping.
- [ ] **Step 2: Add path-escaping regressions.** IDs containing reserved path characters must be quoted consistently before interpolation.
- [ ] **Step 3: Run focused tests and confirm RED.** `python -m unittest tests.test_backend_clients -v`
- [ ] **Step 4: Implement thin client methods.** Keep `_request_json()` as the single JSON transport/error adapter. Each public method only maps typed arguments to the existing q_flow route; do not add CashflowPot business logic to the client.
- [ ] **Step 5: Run focused tests GREEN.** `python -m unittest tests.test_backend_clients -v`
- [ ] **Step 6: Commit quollnet-mcp.** `git add quollnet_mcp/services/qflow_client.py tests/test_backend_clients.py && git commit -m "feat: expand CashflowPot backend client"`

---

## Task 7: Implement dedicated MCP schemas and project/cashflow tools

**Repository:** `iqmia/quollnet-mcp`

**Files:**
- Create: `quollnet_mcp/cashflowpot/models.py`
- Create: `quollnet_mcp/cashflowpot/auth.py`
- Create: `quollnet_mcp/cashflowpot/tools/__init__.py`
- Create: `quollnet_mcp/cashflowpot/tools/projects.py`
- Create: `quollnet_mcp/cashflowpot/tools/cashflows.py`
- Create: `tests/test_cashflowpot_projects.py`
- Create: `tests/test_cashflowpot_cashflows.py`

**Shared auth helper:**

```python
async def cashflowpot_token(unit_id: str | None = None) -> str:
    """Exchange the connected MCP token for a normal CashflowPot app/unit token."""
```

Use the existing shared `qauth_client.exchange_app_token`; app token for discovery/create, unit token for project-scoped operations.

- [ ] **Step 1: Define Pydantic input schemas from the current portable contract.** Cashflow schema includes all source commercial/inflow fields and embedded facilities/activities as appropriate. Activity schema must distinguish generated Work, Manual Work, and Scheduled Cost without calculating derived arrays client-side.
- [ ] **Step 2: Write project tool tests first.** Cover all seven project tools, app-token vs unit-token exchange, backend method mapping, returned payload passthrough, and QAuth/qFlow errors becoming concise `ToolError`s.
- [ ] **Step 3: Write cashflow tool tests first.** Cover `get_cashflow`, `get_cashflow_results`, create/update/delete/restore/hard-delete, `export_cashflow_json`, and `import_cashflow_json`. Verify portable JSON is backend-returned rather than reconstructed in MCP.
- [ ] **Step 4: Run focused tests and confirm RED.** `python -m unittest tests.test_cashflowpot_projects tests.test_cashflowpot_cashflows -v`
- [ ] **Step 5: Implement auth helper and project tools.** Do not infer permissions; only exchange the connected MCP identity and forward to q_flow.
- [ ] **Step 6: Implement cashflow tools.** Keep percentages as fractions and periods zero-based in tool schemas/descriptions; `get_cashflow_results` should return a compact calculation-focused subset taken from the authoritative backend snapshot, not recalculate it.
- [ ] **Step 7: Run focused tests GREEN.** `python -m unittest tests.test_cashflowpot_projects tests.test_cashflowpot_cashflows -v`
- [ ] **Step 8: Commit quollnet-mcp.** `git add quollnet_mcp/cashflowpot/models.py quollnet_mcp/cashflowpot/auth.py quollnet_mcp/cashflowpot/tools tests/test_cashflowpot_projects.py tests/test_cashflowpot_cashflows.py && git commit -m "feat: add CashflowPot project and cashflow tools"`

---

## Task 8: Implement Activity, facility, and Excel MCP tools and register the full tool set

**Repository:** `iqmia/quollnet-mcp`

**Files:**
- Create: `quollnet_mcp/cashflowpot/tools/activities.py`
- Create: `quollnet_mcp/cashflowpot/tools/facilities.py`
- Create: `quollnet_mcp/cashflowpot/tools/exports.py`
- Modify: `quollnet_mcp/cashflowpot/tools/__init__.py`
- Modify: `quollnet_mcp/cashflowpot/server.py`
- Create: `tests/test_cashflowpot_activities.py`
- Create: `tests/test_cashflowpot_facilities.py`
- Create: `tests/test_cashflowpot_exports.py`
- Modify: `tests/test_cashflowpot_server.py`

**Final dedicated tool names:**

```text
Projects
  list_cashflow_projects
  get_cashflow_project
  create_cashflow_project
  update_cashflow_project
  delete_cashflow_project
  restore_cashflow_project
  hard_delete_cashflow_project

Cashflows
  get_cashflow
  get_cashflow_results
  create_cashflow
  update_cashflow
  delete_cashflow
  restore_cashflow
  hard_delete_cashflow
  export_cashflow_json
  import_cashflow_json

Activities
  get_activity
  get_activity_types
  list_deleted_activities
  create_activity
  update_activity
  delete_activity
  restore_activity
  restore_activities
  hard_delete_activity

Facilities
  list_financing_facility_presets
  list_financing_facilities
  get_financing_facility
  add_financing_facility
  update_financing_facility
  delete_financing_facility
  set_financing_facility_order

Exports
  export_cashflow_excel
```

- [ ] **Step 1: Write Activity tests first.** Verify Work S-curve/linear/manual and Scheduled Cost payloads forward source fields unchanged, including dense local schedule and zero-based `start`; restore-many maps the ID list exactly.
- [ ] **Step 2: Write facility tool tests first.** Ensure individual convenience tools call the atomic q_flow facility endpoints; the MCP must never fetch/rewrite the whole array itself. Test presets/list/get/add/update/delete/order and backend validation propagation.
- [ ] **Step 3: Write Excel tool tests first.** `export_cashflow_excel` exchanges a unit token, calls q_flow's export-metadata endpoint, and returns filename/download URL/expiry. Do not fetch, base64, cache, or proxy the XLSX through MCP.
- [ ] **Step 4: Write registration/annotation tests.** Register exactly the approved dedicated tool names. Read tools get `read_only_hint=True`; hard-delete and delete tools get `destructive_hint=True`; normal creates/updates are mutating but not destructive. Assert these tools are registered on the dedicated server only; existing `/mcp` registrations stay unchanged.
- [ ] **Step 5: Run focused tests and confirm RED.** `python -m unittest tests.test_cashflowpot_activities tests.test_cashflowpot_facilities tests.test_cashflowpot_exports tests.test_cashflowpot_server -v`
- [ ] **Step 6: Implement Activity tools.** Preserve backend validation messages and return authoritative snapshots after mutation.
- [ ] **Step 7: Implement facility tools.** Treat facility objects as embedded source definitions addressed by stable ID; no MCP-side facility persistence or finance math.
- [ ] **Step 8: Implement Excel tool.** Return q_flow's stateless signed URL metadata verbatim plus a concise user-facing description; add an MCP `ResourceLink` only if the SDK/client behavior is straightforward and does not replace the URL compatibility path.
- [ ] **Step 9: Register full dedicated tool surface.** Keep `quollnet_mcp/tools/cashflowpot.py` and its two existing `/mcp` compatibility tools untouched.
- [ ] **Step 10: Run focused tests GREEN.** `python -m unittest tests.test_cashflowpot_activities tests.test_cashflowpot_facilities tests.test_cashflowpot_exports tests.test_cashflowpot_server -v`
- [ ] **Step 11: Commit quollnet-mcp.** `git add quollnet_mcp/cashflowpot tests/test_cashflowpot_activities.py tests/test_cashflowpot_facilities.py tests/test_cashflowpot_exports.py tests/test_cashflowpot_server.py && git commit -m "feat: expose full CashflowPot MCP tool set"`

---

## Task 9: Documentation, full regression, and deployment configuration

**Repositories:** `iqmia/q_flow`, `iqmia/quollnet-mcp`

**Files:**
- Modify: `iqmia/q_flow/README.md`
- Modify: `iqmia/q_flow/documentation/technical.md`
- Modify: `iqmia/q_flow/documentation/deployment.md`
- Modify: `iqmia/quollnet-mcp/readme.md`
- Modify: `iqmia/quollnet-mcp/.env.example`
- Modify tests only if full-suite regressions expose missing coverage

- [ ] **Step 1: Update q_flow docs.** Backend now owns portable JSON export and Excel generation; document facility atomic routes and stateless signed Excel links. Clarify that no generated XLSX files are retained.
- [ ] **Step 2: Update MCP docs/config example.** Document both endpoints, shared QAuth identity exchange, `CASHFLOWPOT_MCP_RESOURCE_URI`, production `QFLOW_BASE_URL=https://cashflowpot.com/api/`, the complete CashflowPot tool categories, and that `/mcp` is intentionally unchanged.
- [ ] **Step 3: Run the full q_flow backend suite.** From `iqmia/q_flow`: `pytest -q`. Fix only regressions caused by this work, then rerun until green.
- [ ] **Step 4: Run the full quollnet-mcp suite.** From `iqmia/quollnet-mcp`: `python -m unittest discover -s tests -v`. Confirm existing QArticles/qTools/current CashflowPot compatibility tests still pass.
- [ ] **Step 5: Run the five high-risk review checks explicitly.** Verify: (1) signed URL tamper/expiry/no-storage behavior; (2) facility ID/order/rollback atomicity; (3) Manual Work/Scheduled Cost and zero-based periods; (4) long financing horizon extending Excel columns/charts; (5) `/mcp` vs `/cashflowpot` audience/path isolation.
- [ ] **Step 6: Commit documentation/regression fixes in each affected repo.** Use focused commits, e.g. `docs: document CashflowPot MCP backend exports` and `docs: document dedicated CashflowPot MCP endpoint`.
- [ ] **Step 7: Configure QAuth in production; no q_auth code change.** On the existing QAuth MCP gateway application, add exactly `https://mcp.quollnet.com/cashflowpot` to `mcp_oauth.resources`; leave the existing `/mcp` resource in place. Confirm CashflowPot still has `allow_quollnet_mcp_exchange=true`.
- [ ] **Step 8: Deploy q_flow first.** Pull q_flow, install the updated Python requirements in the existing venv, configure `PUBLIC_API_BASE_URL`/TTL, restart `cashflowpot`, and verify `/api/health`, portable export, facility mutation, export-link creation, and an in-memory XLSX download.
- [ ] **Step 9: Deploy quollnet-mcp second.** Pull, install requirements if needed, set `CASHFLOWPOT_MCP_RESOURCE_URI` and production `QFLOW_BASE_URL`, restart the existing MCP service, then verify `/mcp` still works and `/cashflowpot` performs OAuth with the dedicated audience.
- [ ] **Step 10: End-to-end acceptance.** Through the dedicated MCP connection: list/create/update project; create/import/export scenario; CRUD Work and Scheduled Cost Activities; CRUD/reorder facilities; read results/KPIs; request Excel export; open the signed URL; confirm the file matches the approved report and that no XLSX remains on the server.

---

## Review focus before merge/deploy

1. **Excel URL security:** the signed token is short-lived, tamper-evident, scoped to cashflow+unit, carries no QAuth bearer token, and the public GET cannot switch to another cashflow by changing path/body data.
2. **Embedded-facility atomicity:** a failed update must not partially mutate the JSON list; IDs remain stable; ordering is deterministic; recalculation happens before commit.
3. **Activity semantics:** Manual Work and Scheduled Cost preserve dense local schedule + zero-based start conventions and let q_flow derive cost/duration.
4. **Report horizon/parity:** financing periods that extend beyond Work duration must extend headers, rows, totals, charts, and print geometry without truncation.
5. **MCP isolation:** `/cashflowpot` and `/mcp` share infrastructure but not audiences/tool registries; adding the dedicated endpoint must not broaden or alter the existing central MCP behavior.

## Completion criteria

Implementation is complete only when both full test suites pass, the dedicated QAuth resource is configured, an end-to-end `/cashflowpot` connection can exercise the approved tool surface, and an Excel export downloads from a signed URL while leaving **zero generated XLSX files** in server storage.
