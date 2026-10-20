# CashflowPot MCP submission audit

Reviewed 20 October 2026 against the official plugin guidelines, remote MCP review requirements and metadata guidance. This records source changes and local test coverage; it is not an OpenAI approval or a production OAuth test.

## Effective properties and modeling defaults

`get_cashflow_results` keeps its existing result keys and adds `properties.contract`, `properties.forecast`, `properties.activities`, `properties.financing` and unit conventions. Values are projected from the existing q_flow scenario snapshot. No finance calculations, duplicated default resolver, or provenance tracking are added to MCP. Instructions require a concise explanation of material properties when creating/explaining/comparing forecasts and relevant changes on follow-up edits. The legacy `outflow_with_interest` key is documented as a cumulative balance.

New bank facilities (Letter of Credit, Overdraft, PPC Discount, Working Capital, Equipment Loan) receive an editable interest rate of **0.005 per model period**. Their omitted fees resolve to **facility value × 0.5% ÷ 12**, rounded to two decimals and charged once at start. Value is the limit, or scheduled draw total when no limit is set; unlimited facilities without a known value require an entered fee and otherwise retain a disclosed zero fallback. Owner’s Injection, Other and custom types default to zero interest and fees. These are editable modeling defaults to replace with lender terms. No annual/monthly convention is inferred. Existing saved facilities and explicitly entered zero costs remain unchanged. Resolved fees remain fixed on later limit/schedule edits. New creation/import boundaries resolve product defaults in q_flow; the calculator is unchanged. The preset response exposes `default_fees_rate` and `default_fees_basis` as catalog metadata alongside the resolved numeric fee in facility responses.

## Input and output contracts

- Existing descriptive tool names are retained for compatibility. Descriptions now identify purpose, limits, persistent effects, retry behavior and simulation-only financing.
- Source payloads are typed and reject unknown fields. Backend-supported enums, finite amounts, fraction ranges, zero-based periods and numeric schedules are documented. Portable format/version are constrained. Editable category/unit text remains flexible.
- Closed output contracts recursively project only relevant project/scenario/activity/facility identifiers, source properties, calculated finance data and required download metadata. Project tools return compact scenario summaries.
- Refreshed backend tokens, keys, user/audit identifiers, timestamps, role/photo data, diagnostics, cached per-activity arrays and unknown fields are removed. Success messages are allowlisted. Backend errors/auth-exchange errors use safe messages rather than echoing SQL/upstream bodies.
- Permanent deletion requires `confirm_permanent=true`; false/omission is rejected before auth exchange or backend access. It supplements client safeguards and backend permission checks, and is not proof of human consent by itself.

## All 33 tools and annotation rationale

`R` = readOnlyHint, `D` = destructiveHint, `O` = openWorldHint. Every hint is explicit. All tools are restricted to the connected CashflowPot account/project or its bounded preset catalog; none accepts arbitrary destinations or operates on public/open-ended entities, so O is false throughout. Overwriting edits and reversible deletion also use D=true. Current guidelines say annotation justifications are no longer mandatory; the rationale is retained for review and older dashboard fields.

| Tool | R | D | O | Rationale |
|---|---|---|---|---|
| `list_cashflow_projects` | true | false | false | Read-only project discovery; compact identities and descriptions, pagination only. |
| `get_cashflow_project` | true | false | false | Read-only project discovery; compact active scenarios, no duplicate result arrays. |
| `create_cashflow_project` | false | false | false | Additive creation of a QAuth project and empty base scenario; retries can duplicate. |
| `update_cashflow_project` | false | true | false | Overwrites project metadata; destructive hint reflects replacement. |
| `delete_cashflow_project` | false | true | false | Deactivates access; retained local scenarios can be restored. |
| `restore_cashflow_project` | false | false | false | Reactivates existing data without deleting or replacing source properties. |
| `hard_delete_cashflow_project` | false | true | false | Irreversibly removes QAuth project plus all local scenarios/activities; explicit confirmation required. |
| `get_cashflow` | true | false | false | Stateless calculation/read of saved source and financial outputs. |
| `get_cashflow_results` | true | false | false | Stateless calculation/read plus effective properties; no inferred defaults or provenance. |
| `create_cashflow` | false | false | false | Additive scenario creation; backend validation/calculation; retries can duplicate. |
| `update_cashflow` | false | true | false | Overwrites contract/forecast properties and recalculates. |
| `delete_cashflow` | false | true | false | Hides the scenario using a retained deletion flag; forecast access changes. |
| `restore_cashflow` | false | false | false | Reactivates retained scenario without replacing source. |
| `hard_delete_cashflow` | false | true | false | Irreversibly removes scenario, activities and embedded facilities; explicit confirmation required. |
| `export_cashflow_json` | true | false | false | Stateless source-only export; no saved artifact or ownership metadata. |
| `import_cashflow_json` | false | false | false | Additive scenario import; independent of other plugins; retries can duplicate. |
| `get_activity` | true | false | false | Read-only activity source; cached per-activity arrays and audit metadata omitted. |
| `get_activity_types` | true | false | false | Stateless bounded preset catalog; no user data. |
| `list_deleted_activities` | true | false | false | Read-only retained deleted activity source list. |
| `create_activity` | false | false | false | Adds source activity and recalculates; retries can duplicate. |
| `update_activity` | false | true | false | Overwrites supplied activity source fields and recalculates. |
| `delete_activity` | false | true | false | Hides retained activity and changes the active forecast; restore is available. |
| `restore_activity` | false | false | false | Restores retained source and recalculates; no overwriting/deletion. |
| `restore_activities` | false | false | false | Restores selected retained activities; every affected parent is authorized. |
| `hard_delete_activity` | false | true | false | Irreversibly erases activity and recalculates atomically; explicit confirmation required. |
| `list_financing_facility_presets` | true | false | false | Stateless bounded catalog including illustrative cost notes and units. |
| `list_financing_facilities` | false | false | false | May assign/persist missing legacy IDs. Financial properties do not change; additive ID assignment is not destructive. |
| `get_financing_facility` | false | false | false | May assign/persist missing legacy IDs before lookup; no financial-property replacement. |
| `add_financing_facility` | false | false | false | Adds simulated facility and recalculates; does not transact with a bank. |
| `update_financing_facility` | false | true | false | Overwrites simulated facility properties and recalculates. |
| `delete_financing_facility` | false | true | false | Removes embedded facility definition with no restore endpoint. |
| `set_financing_facility_order` | false | true | false | Overwrites order and sweep priorities; can change funding and repayment results. |
| `export_cashflow_excel` | true | false | false | Stateless signed download capability. No artifact/job is persisted; XLSX is generated in memory on download. Expiry is necessary download metadata. |

## Verification and release boundary

Run `python -m unittest discover -q` in quollnet-mcp and `python -m pytest -q` in q_flow. Contract tests validate advertised input/output schemas and output minimization. Wire tests exercise all 33 tool registrations with realistic mocked backend envelopes, checking both text and structured content. Isolated SQLite backend tests cover permission denial, parent scoping, cascading permanent deletion, repeat/missing IDs, QAuth failures with no local loss, and calculation failure rollback. Regression tests also cover partial activity edits and portable legacy-null round trips.

Deploy the q_flow change before the MCP change. Reconnect or refresh the development integration so it sees the new schemas/confirmation argument. Run a fresh-account OAuth flow and the official portal tool scan against the deployed build before submission. These local tests mock the QAuth service boundary and do not certify production OAuth/revocation behavior. No live user project was deleted during testing.

Project permanent deletion still calls QAuth before local database cleanup; those two services do not share a distributed transaction. Existing error/retry handling remains a deployment consideration, not a newly introduced behavior.

## Verified results

- quollnet-mcp: **191 tests passed**, including 40 wire tests exercising all 33 public tools, schema validation, identity/permission failures and both response channels.
- q_flow: **404 tests passed**, with existing dependency/SQLAlchemy deprecation warnings. Coverage includes facility-value fee defaults across add/import/new scenario creation, explicit overrides, one-time fee charging, saved-value preservation and invalid fee-basis validation. Explicit null facility start/interest/fees fail validation atomically rather than reaching a calculator error.
- Both repositories pass `git diff --check`. Independent review found no remaining blocker after the legacy-null and schedule-schema fixes.
- Backend suites must run serially: existing legacy tests share an on-disk SQLite fixture. An earlier concurrent verification run collided in decorator/database tests with table-already-exists errors; isolated serial runs pass without application changes for that test-run collision.

## Official sources

- https://developers.openai.com/plugins/plugin-guidelines
- https://developers.openai.com/plugins/deploy/app-review
- https://developers.openai.com/plugins/guides/optimize-metadata
