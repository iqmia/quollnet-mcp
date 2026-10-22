# MCP document workflow implementation evidence

## Scope

The QLedger/QEntries MCP surface now advertises 56 tools. File upload takes an
OpenAI file reference instead of base64; original bounded bytes are downloaded and
forwarded as multipart. Operation files are an ordered list aligned with
`operation.attachments`, because OpenAI file parameters support a top-level file
object or array rather than an arbitrary keyed map. Backend part names are intact.

The official contract was independently checked on 22 October 2026 at
https://developers.openai.com/plugins/reference#define-file-inputs. It requires
`download_url` and `file_id`, declares optional `mime_type` and `file_name`, and
allows extra optional properties. `filename` is accepted as an optional alias.
Upload advertises `openai/fileParams: ["file"]`; operations advertise `["files"]`.
There is no advertised base64 alternative.

Download security: narrow OpenAI file host families, HTTPS only, no URL credentials,
standard TLS port only, public non-reserved/non-multicast DNS results only, and a
pinned checked IP with original TLS SNI/Host. A dedicated transport has no environment
proxy, cookies, backend token, redirects or normal HTTP-client URL logging. Remote
errors omit signed URLs and upstream bodies. Byte/aggregate limits are enforced.

The tools distinguish protected metadata links, signed expiring/revocable public
shares, authenticated binary inspection, saved DRAFT preview metadata, atomic final
issuance, preserved issued metadata retrieval and terminal cancelled/superseded
status changes. Final PDFs, evidence protection and verification are backend
responsibilities. OCR guidance requires a real separate `.txt` attachment linked to
the original using `text`/`ocr`, with optional companion provenance Records.

## Verification

- Added workflow/security tests first and observed missing-contract failures before
  implementation; green after implementation.
- Separately reproduced signed-query logging at HTTP-client INFO and multicast DNS
  acceptance, then fixed both with regression tests (RED to GREEN).
- `python -m unittest discover -s tests -q`: 246 tests, OK (23.152 seconds).
- Ruff checks pass for changed implementation files and the new
  `tests/test_qledger_file_inputs.py`; these files also pass Ruff formatting.
- `git diff --check`: clean.
- Broad QLedger Ruff check still reports 53 pre-existing import/style findings in
  other implementation/test lines; unrelated cleanup is excluded.

These are controlled upstream/ASGI tests. Live ChatGPT file delivery, TLS host
reachability and deployed backend integration require acceptance verification after
the coordinated backend changes are available. No production action was performed.

## Integration review follow-up

The integration reviewer reproduced a signed URL leak before tool execution:
MCP 2.0's generated outer argument model included the entire file object in a
missing-`file_id` validation error. `FileInput` representation settings do not
control that outer model. Registered argument models now use
`hide_input_in_errors=True` and rebuild their Pydantic validators before serving
requests. This retains field locations and validation reasons while suppressing
input values for every QLedger tool.

Actual `server.call_tool` regression tests reproduced the failure first, then
passed for single/batch missing file IDs, missing unit, invalid MIME values,
unsafe URLs and filenames. The relation guidance now explicitly keeps all labels
caller-defined; `draft_pdf`/`issued_pdf` are conventions, while issued-document
metadata and verification establish issuance status.

Final follow-up validation: 249 tests passed in 19.479 seconds via
`python -m unittest discover -s tests -q`; changed files passed Ruff/formatting
and `git diff --check`.

## Optional MIME inference

A real file reference may omit its optional `mime_type`. A generic/default MIME
now uses a safe, syntactically valid response Content-Type without parameters;
absent, invalid or generic response types fall back to the supplied filename's
standard MIME mapping, then `application/octet-stream`. An explicitly supplied
non-generic MIME is preserved. Bytes and filename selection are unchanged.

The omitted-MIME PNG regression failed first and then passed. Coverage also checks
PDF filename fallback, invalid/generic headers, unknown filenames and explicit JPEG
precedence. Full suite: 250 tests passed in 18.761 seconds. Changed-file Ruff,
formatting and `git diff --check` passed.
