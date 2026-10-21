# QLedger API-to-tool mapping

Date: 17 October 2026. Draft companion to `2026-10-17-qledger-mcp-design.md`.

Source: `quollnet/q_ledger@92fc071e04583369e8d7746a91f3e16a59470c81`. Covers all existing business routes in `api/units.py`, `accounts.py`, `settings.py`, `journals.py`, `reports.py`, `records.py`, `attachments.py`, `operations.py`. Login/callback/webhook/refresh/fresh are infrastructure, not model-callable accounting tools.

Notation: `U` means `/api/units/{unit_id}`; `E` is a journal entry ID, `R` record ID, `A` attachment ID, `L` link ID. Every `{...}` ID is explicitly supplied, UUID-validated where the API requires it. `K` means required `idempotency_key` mapped to the header. No tools accept a token, raw URL, HTTP verb or fabricated role grant from the model.

## Units and membership — `tools/units.py`

| Tool | API | Token / permission | Special behavior |
|---|---|---|---|
| `list_qledger_units` | GET `/api/units` | Application user | Preserve pagination |
| `create_qledger_unit` | POST `/api/units` | Application user | UnitCreate; strip returned token |
| `load_qledger_unit` | POST `U/load` | Application user | Strip token; return sanitized hierarchy |
| `list_qledger_members` | GET `U/members` | Unit / `view:member` | Preserve members/all_roles/pagination |
| `invite_qledger_member` | POST `U/members/invite` | Unit / `invite:member` | Email, roles, send_email, next; may send a real invitation |
| `remove_qledger_member` | DELETE `U/members/{user_id}` | Unit / `remove:member` | Destructive annotation |
| `list_qledger_roles` | GET `U/roles` | Unit / `view:role` | Actual backend role names |
| `add_qledger_member_roles` | POST `U/members/{user_id}/roles` | Unit / `edit:member` | Explicit role list; not replace-all |
| `remove_qledger_member_role` | DELETE `U/members/{user_id}/roles/{role_name}` | Unit / `edit:member` | Encode path segment safely |

QLedger does not expose unit edit/delete, role creation or permission editing routes in this API. Do not add tools that bypass QLedger to invent that surface.

## Accounts and settings — `tools/accounts.py`, `tools/settings.py`

| Tool | API | Permission | Input |
|---|---|---|---|
| `list_qledger_accounts` | GET `U/accounts` | `account:view` | Page query |
| `get_qledger_account` | GET `U/accounts/{account_id}` | `account:view` | ID |
| `create_qledger_account` | POST `U/accounts` | `account:write` | AccountCreate |
| `update_qledger_account` | PATCH `U/accounts/{account_id}` | `account:write` | AccountPatch, version |
| `get_qledger_settings` | GET `U/settings` | `settings:view` | Unit |
| `initialize_qledger_settings` | PUT `U/settings` | `settings:write` | SettingsCreate |
| `update_qledger_settings` | PATCH `U/settings` | `settings:write` | SettingsPatch, version |

Account type and normal balance are create-time fields, not patch fields. Deactivate via `is_active`; no account-delete endpoint. Settings base-currency/lock restrictions remain backend-owned.

## Transactions — `tools/journals.py`

| Tool | API | Permission | Input / invariant |
|---|---|---|---|
| `list_qledger_transactions` | GET `U/journal-entries` | `journal:view` | Page/date range |
| `get_qledger_transaction` | GET `U/journal-entries/E` | `journal:view` | Return version and reviewed_evidence unchanged |
| `create_qledger_transaction` | POST `U/journal-entries` | `journal:write` | K; JournalCreate; returns draft |
| `update_qledger_transaction` | PATCH `U/journal-entries/E` | `journal:write` | JournalPatch, version; lines replace supplied line collection |
| `post_qledger_transaction` | POST `U/journal-entries/E/post` | `journal:post` | PostRequest: reviewed version/evidence, explicit optional lock override |
| `reverse_qledger_transaction` | POST `U/journal-entries/E/reverse` | `journal:reverse` | K; supplied date/description; new draft |
| `delete_qledger_transaction` | DELETE `U/journal-entries/E` | `journal:delete` | Eligible draft only; backend has no version body here |

Posting also requires any capabilities QLedger checks for affected records/evidence. No helper may bypass those checks. No automatic posting after create or reverse.

## Reports — `tools/reports.py`

| Tool | API | Permission |
|---|---|---|
| `get_qledger_ledger` | GET `U/ledger` | `ledger:view` |
| `get_qledger_account_statement` | GET `U/accounts/{account_id}/statement` | `soa:view` |
| `get_qledger_partner_statement` | GET `U/accounts/{account_id}/partner-statement` | `soa_partner:view` |
| `get_qledger_trial_balance` | GET `U/trial-balance` | `ledger:view` |

All use the API LedgerQuery contract (page/per_page/date_from/date_to/optional account_id). Return backend totals/balances; do not sum an incomplete page as a complete ledger.

## Records — `tools/records.py`

| Tool | API | Permission | Input / invariant |
|---|---|---|---|
| `list_qledger_records` | GET `U/records` | `record:view` | Target pair, namespace, comma-separated types, page |
| `get_qledger_record` | GET `U/records/R` | `record:view` | Includes reviewed_attachments |
| `create_qledger_record` | POST `U/records` | `record:add` | K; RecordCreate; initial links need target/link grants |
| `update_qledger_record` | PATCH `U/records/R` | `record:edit` | RecordPatch, version; draft content only |
| `delete_qledger_record` | DELETE `U/records/R` | `record:delete` | VersionRequest body; eligible unposted orphan only |
| `copy_qledger_record` | POST `U/records/R/copy` | `record:add` plus source view | K; VersionRequest; unlinked draft copy |
| `post_qledger_record` | POST `U/records/R/post` | `record:post` | RecordPost: version, exact reviewed_attachments |
| `list_qledger_record_links` | GET `U/records/R/links` | `record:view` | Only visible parent links |
| `link_qledger_record` | POST `U/records/R/links` | `record:link` plus target grants | K; RecordLinkCreate; reviewed source fields when posting |
| `unlink_qledger_record` | DELETE `U/records/R/links/L` | `record:unlink` plus parent grants | Physical unlink; may recursively delete eligible orphans |
| `replace_qledger_record_link` | PATCH `U/records/R/links/L` | `record:unlink` plus link/target grants | Atomic RecordLinkCreate replacement; not unlink-then-create |

Mutation responses can be only `{id, version, status}` without record:view. Preserve that response rather than manufacturing or looking up full content.

## Attachments — `tools/attachments.py`

| Tool | API | Input / invariant |
|---|---|---|
| `list_qledger_attachments` | GET `U/attachments` | Required target type/ID, namespace, page |
| `get_qledger_attachment` | GET `U/attachments/A` | Authorized metadata/visible links |
| `upload_qledger_attachment` | POST `U/attachments` | K; strict base64 -> multipart file + canonical initial-parent fields |
| `download_qledger_attachment` | GET `U/attachments/A/download` | Bounded bytes -> authenticated binary resource; preserve original bytes |
| `list_qledger_attachment_links` | GET `U/attachments/A/links` | Backend-filtered links |
| `link_qledger_attachment` | POST `U/attachments/A/links` | K; TargetRef |
| `unlink_qledger_attachment` | DELETE `U/attachments/A/links/L` | Parent permissions; backend cleanup |
| `replace_qledger_attachment_link` | PATCH `U/attachments/A/links/L` | Atomic TargetRef replacement |

Resource reader: `qledger://units/{unit_id}/attachments/{attachment_id}`. Calls the same authenticated download path and checks limits on every read.

All permissions follow backend parent paths: account:view/write, journal:view/write, record:view/link/unlink, view:member/edit:member, view:unit/edit:unit as appropriate. Attachment-as-parent traverses an authorized path. Posted-parent protection and orphan cleanup remain backend decisions. There is no independent attachment deletion/posting tool.

## Atomic operation — `tools/operations.py`

| Tool | API | Input / invariant |
|---|---|---|
| `execute_qledger_operation` | POST `U/operations` | K; OperationRequest plus optional named files; all applicable permissions checked by QLedger |

Use JSON when no files are supplied; otherwise one multipart `payload` JSON part plus the exactly named file parts. No missing, duplicate, reused or unreferenced file fields. References use kind + exactly one id/key. Local keys are unique, `journal` is reserved and `journal:1` etc. address new lines. Existing record references carry reviewed versions/hashes if they may post. Do not implicitly set `post_journal` or add `post_records`; preserve the authorized payload. Return OperationResult local-key -> server-ID maps.

## Registration contract

There are 47 tools: 9 unit/member, 4 account, 3 settings, 7 journal, 4 report, 11 record, 8 attachment and 1 operation. All use the existing OAuth security metadata. Read tools use read-only/non-destructive hints; deletes/unlinks/replacements, posting, access changes and mutable updates carry accurate destructive hints. Creation is not broadly advertised as idempotent unless the tool requires a backend-supported key. Hints guide clients; they never grant permissions or replace authorization.
