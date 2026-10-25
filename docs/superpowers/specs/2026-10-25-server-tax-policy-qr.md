# QEntries tax policy, party identity and verification QR

Approved scope: implement the preceding discussion on feature/mcp-checksums-line-guidance in both repositories; preserve get_qledger_line_item_guidance. No merge or deployment.

QEntries owns a country/type strategy registry and read-only POST /tax-identifiers/check. PT NIF/NIPC implements the existing proven checksum; other country/type pairs are unsupported and accepted without override. No tax authority lookup or claim of registration. Preserve exact input. Structured checks distinguish missing, invalid format, failed/passed checksum, unsupported; acceptance is separate.

Native unit remains workspace/access scope. Live party records hold legal/contact/tax identity; one native unit link with relation unit_legal_entity identifies its legal entity. unit_info is the live settings record, not duplicate company identity. An optional unit-linked unit_info.data.tax_identifiers object sets required=false, check_when_present=true, enforce_checksum=false defaults. Absence of config is permissive. Ambiguous active configs/legal entities fail explicitly. Policy mutations require settings:write as well as normal record/target permissions.

Canonical party.data.tax_identifiers is a list of country_code, identifier_type (tax_id/nif/nipc/vat etc), identifier. tax_validation is server-owned, stored separately from printable fields. Optional missing and unsupported foreign values may be saved/used. Required missing or explicitly enforced failed checks require explicit tax_override with reason and record:tax_override permission. Merely holding permission does not exercise it. Acceptance records actual actor/time/reason and binds exact identifier/country/type; edits invalidate stale acceptance. Ordinary failed checks are advisory. Templates are excluded.

Finalization rechecks canonical tax identifiers and explicit document party references against current unit policy; issuer uses unit_legal_entity fallback. Required policy requires issuer/counterparty references for issued commercial documents. No new universal fiscal/legal requirements. Document rendering remains reviewed content; AI copies only printable party facts, never internal validation/override commentary. No dynamic changes to reviewed identity rendering during issue.

MCP forwards checking to QEntries with explicit country, exposes policy result; no local algorithms. Instructions/catalog explain party/unit settings, optional/required/unsupported/overridden and keep override audit out of PDF. Retain typed line guidance.

Every issued QTypeset document includes a visible server verification QR in the closing/signature area (default align right), using only actual server URL. Preserve a valid custom QR placement; repair absent/unreferenced/wrong-type declarations, fail rather than silently omit when limits prevent insertion. Preview has no live verification URL; final URL assigned on issue. This is document verification, not a cryptographic signature or tax authority certification. Existing issued PDFs unchanged.

Approach: extend existing generic records/services and issued rendering, no new DB columns/migration. Avoid new dedicated policy record type and avoid duplicating issuer identity in unit_info. Existing legacy JSON remains supported; canonical policy enforcement uses documented fields rather than guessing arbitrary JSON keys.
