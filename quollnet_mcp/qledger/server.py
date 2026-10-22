"""Dedicated QLedger surface; shares OAuth infrastructure, never accounting authority."""

import base64

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from mcp.types import ToolAnnotations

from quollnet_mcp.auth import QAuthTokenVerifier
from quollnet_mcp.config import Settings
from quollnet_mcp.qledger.files import attachment_resource
from quollnet_mcp.qledger.instructions import QLEDGER_INSTRUCTIONS
from quollnet_mcp.qledger.tools import (
    accounts,
    attachments,
    documents,
    journals,
    operations,
    records,
    reports,
    units,
)
from quollnet_mcp.qledger.tools import (
    settings as ledger_settings,
)

_GROUPS = (
    (
        units,
        (
            "list_qledger_units",
            "create_qledger_unit",
            "load_qledger_unit",
            "list_qledger_members",
            "invite_qledger_member",
            "remove_qledger_member",
            "list_qledger_roles",
            "add_qledger_member_roles",
            "remove_qledger_member_role",
        ),
    ),
    (
        accounts,
        (
            "list_qledger_accounts",
            "get_qledger_account",
            "create_qledger_account",
            "update_qledger_account",
        ),
    ),
    (
        ledger_settings,
        (
            "get_qledger_settings",
            "initialize_qledger_settings",
            "update_qledger_settings",
        ),
    ),
    (
        journals,
        (
            "list_qledger_transactions",
            "list_qledger_classification_values",
            "get_qledger_transaction",
            "create_qledger_transaction",
            "update_qledger_transaction",
            "post_qledger_transaction",
            "reverse_qledger_transaction",
            "delete_qledger_transaction",
        ),
    ),
    (
        reports,
        (
            "get_qledger_ledger",
            "get_qledger_account_statement",
            "get_qledger_partner_statement",
            "get_qledger_trial_balance",
        ),
    ),
    (
        records,
        (
            "list_qledger_records",
            "get_qledger_record",
            "create_qledger_record",
            "update_qledger_record",
            "delete_qledger_record",
            "copy_qledger_record",
            "post_qledger_record",
            "unpost_qledger_record",
            "list_qledger_record_links",
            "link_qledger_record",
            "unlink_qledger_record",
            "replace_qledger_record_link",
        ),
    ),
    (
        attachments,
        (
            "list_qledger_attachments",
            "get_qledger_attachment",
            "create_qledger_attachment_share",
            "revoke_qledger_attachment_share",
            "upload_qledger_attachment",
            "download_qledger_attachment",
            "list_qledger_attachment_links",
            "link_qledger_attachment",
            "unlink_qledger_attachment",
            "replace_qledger_attachment_link",
        ),
    ),
    (operations, ("execute_qledger_operation",)),
    (
        documents,
        (
            "get_qledger_document_design_guidance",
            "render_qledger_record_pdf",
            "issue_qledger_record",
            "get_qledger_issued_document",
            "update_qledger_document_status",
        ),
    ),
)
_KEYED = {
    "issue_qledger_record",
    "create_qledger_transaction",
    "reverse_qledger_transaction",
    "create_qledger_record",
    "copy_qledger_record",
    "link_qledger_record",
    "upload_qledger_attachment",
    "link_qledger_attachment",
    "execute_qledger_operation",
}
_DESCRIPTIONS = {
    "get_qledger_document_design_guidance": "Read advisory document design guidance before creating or changing templates: typography, headers/logos, neutral Issued By/To blocks, tables, totals, spacing, images and issuance snapshots. User preferences override defaults. Set include_schema=true for the native QTypeset v2 contract when designing an unfamiliar layout.",
    "render_qledger_record_pdf": "Render a DRAFT preview of the exact reviewed QEntries record through QTypeset, including posted records. Read design guidance first. Complete native v2 input belongs in record.data.rendering; bind images to authorized attachment IDs. save_to_record=true saves a draft_pdf and requires a stable idempotency_key; its default response_mode=metadata returns URLs without transferring bytes. Unsaved previews default to binary. This never issues or posts. Use issue_qledger_record for final issuance and preserved attachments for historical copies.",
    "get_qledger_issued_document": "Retrieve metadata for the preserved issued PDF and its current verification status, protected_url and verification_url months later. Does not regenerate or transfer binary content.",
    "update_qledger_document_status": "Mark an issued document cancelled or superseded with its exact reviewed version and an explicit reason (max 1000 characters). Requires record:view and record:post. The PDF and posted evidence remain immutable, and accounting journals are unaffected. Status is terminal; an identical status/reason retry is idempotent. Use only with explicit authorization; inspect state after an uncertain response.",
    "issue_qledger_record": "Atomically issue the reviewed document: render its final PDF, preserve exact bytes/checksum, and post the record and reviewed evidence. Requires explicit issuance authorization and exact reviewed version/evidence manifests. Returns attachment/download/verification metadata without binary transfer. Issued records cannot be unposted. Does not create or post accounting entries.",
    "get_qledger_attachment": "Read attachment metadata including protected_url. Use for authenticated download links without transferring binary bytes; protected_url requires user authentication and is not public.",
    "create_qledger_attachment_share": "Create a signed public download URL only when public sharing is requested. Expiry defaults to 3600 seconds (allowed 60..604800). The bearer link grants temporary access to original bytes; it can be revoked.",
    "revoke_qledger_attachment_share": "Revoke the specified signed public share. Original bytes and authorized attachment access are preserved.",
    "list_qledger_attachments": "List attachments linked to a parent, optionally filtered by exact relation. Use issued_pdf for final historical copies, draft_pdf for draft previews.",
    "list_qledger_classification_values": "Discover existing readable chart, project or cost-center names before creating new spellings. Includes live drafts and posted entries, excludes deleted entries. field=chart lists all used charts; project/cost_center are scoped to query.chart (default main). Paginate distinct values; prefix is literal text.",
    "list_qledger_transactions": "Find transactions in one chart (default main), optionally by dates and matching line project, cost-center/code, dotted prefix or account type. Combined line filters must match the same line. Full transactions are returned, including their other lines.",
    "create_qledger_transaction": "Prepare a draft transaction in one chart (default main). Optional project and cost_center are readable text on each line; different lines can use different labels. Reuse existing spellings. Accounting classification stays in account_id.",
    "get_qledger_ledger": "Read posted lines and running balances in one chart (default main). Filter by project, cost_center or dotted cost_center_prefix and account_type. Running balances include earlier matching lines. For expense analysis select account_type=expense; never sum every tagged debit as cost.",
    "get_qledger_trial_balance": "Read account totals and hierarchy rollups in one chart (default main). Optional line filters narrow the totals; a filtered result need not balance. Net expenses are total_debit minus total_credit with account_type=expense. Do not add rolled-up and own balances together.",
    "load_qledger_unit": "Load a unit and its hierarchy. Tokens remain internal; use the returned unit ID explicitly on subsequent tools.",
    "invite_qledger_member": "Invite a member with explicit role names. send_email=true may send an invitation. Requires invite:member.",
    "add_qledger_member_roles": "Add the supplied roles to a member; this does not replace all existing roles. Requires edit:member.",
    "post_qledger_transaction": "Permanently post the exact reviewed journal version and evidence. A 409 requires renewed review; never substitute fresh versions automatically.",
    "reverse_qledger_transaction": "Prepare a NEW draft reversal using the supplied date and description. The backend preserves the original chart, project and cost-center labels while swapping debits and credits. The reversal must remain in its original chart. Posting is a separate authorized operation.",
    "post_qledger_record": "Protect a record and its descendant records by posting. Supply the reviewed version, reviewed_records map and reviewed_attachments hashes. Accounting entries are unaffected.",
    "unpost_qledger_record": "Unpost a non-issued reviewed record version only when no parent record, transaction or journal line is posted. Requires record:post. Descendants retain their own posted state. Accounting journals cannot be unposted.",
    "link_qledger_record": "Link a record to a parent. A posted record, journal or line parent posts its source record and descendants; supply the source's reviewed version, reviewed_records and file hashes.",
    "replace_qledger_record_link": "Atomically replace one record-parent link. Posted-parent protections and recursive orphan rules are enforced by QLedger.",
    "unlink_qledger_record": "Remove one parent link; affected unposted parentless children may be deleted recursively by QLedger.",
    "unlink_qledger_attachment": "Remove one parent link; an attachment with no remaining parent may be deleted by QLedger.",
    "download_qledger_attachment": "Retrieve original bytes as an authenticated binary MCP resource plus file metadata. Default maximum 10 MiB; rendering depends on the client.",
    "upload_qledger_attachment": "Upload an authorized ChatGPT file reference with an initial parent. The adapter downloads bounded original bytes without conversion and forwards multipart data. file_name and filename are optional aliases; default limit 10 MiB.",
    "execute_qledger_operation": "Atomically register records, a NEW journal, files and explicit links, with optional explicitly authorized posting. Existing records that may post need reviewed versions/hashes. Supply files as a list aligned with operation.attachments order. Never split the request into separate creates.",
    "list_qledger_records": "Find authorized records by parent, types and optional is_template flag. To find invoice templates, use types=invoice, is_template=true and the native unit parent. Relation is a caller-defined label. Paginate all matching templates before selecting the suitable family/version/date.",
    "delete_qledger_record": "Delete an eligible unposted parentless record with its current version; QLedger recursively cleans eligible children.",
    "copy_qledger_record": "Copy the specified reviewed source version into a new unlinked draft; requires source view and record:add.",
}


def build_qledger_server(settings: Settings) -> MCPServer:
    server = MCPServer(
        "qledger-mcp",
        version=settings.service_version,
        instructions=QLEDGER_INSTRUCTIONS,
        token_verifier=QAuthTokenVerifier(
            issuer_url=settings.qauth_issuer_url,
            resource_uri=settings.qledger_mcp_resource_uri,
            app_id=settings.qauth_app_id,
            public_key=settings.qauth_public_key,
        ),
        auth=AuthSettings(
            issuer_url=settings.qauth_issuer_url,
            resource_server_url=settings.qledger_mcp_resource_uri,
            required_scopes=["mcp:connect"],
        ),
    )
    for module, names in _GROUPS:
        for name in names:
            title = (
                name.replace("_", " ")
                .replace("qledger", "QLedger")
                .capitalize()
                .replace("qledger", "QLedger")
            )
            read_only = (
                name.startswith(("list_", "get_", "download_"))
                or name == "load_qledger_unit"
            )
            destructive = not read_only and not name.startswith(
                ("create_", "copy_", "upload_", "initialize_")
            )
            description = _DESCRIPTIONS.get(
                name,
                title
                + ". QLedger enforces the connected user's actual permissions and validation.",
            )
            if name in _KEYED:
                description += " Requires a stable idempotency_key; retry unchanged intent with the same key, payload and file bytes."
            server.tool(
                name=name,
                title=title,
                description=description,
                annotations=ToolAnnotations(
                    read_only_hint=read_only,
                    destructive_hint=destructive,
                    idempotent_hint=read_only or name in _KEYED,
                    open_world_hint=False,
                ),
                meta={
                    **(
                        {"openai/fileParams": ["file"]}
                        if name == "upload_qledger_attachment"
                        else {"openai/fileParams": ["files"]}
                        if name == "execute_qledger_operation"
                        else {}
                    ),
                    "securitySchemes": [{"type": "oauth2", "scopes": ["mcp:connect"]}],
                    "openai/toolInvocation/invoking": title,
                    "openai/toolInvocation/invoked": title + " complete",
                },
            )(getattr(module, name))

            # MCP 2.0 builds an outer Pydantic argument model. Its error
            # formatting, rather than FileInput's repr/config, governs nested
            # validation failures and otherwise echoes complete signed URLs.
            argument_model = server._tool_manager.get_tool(name).fn_metadata.arg_model
            argument_model.model_config["hide_input_in_errors"] = True
            argument_model.model_rebuild(force=True)

    @server.resource(
        "qledger://units/{unit_id}/attachments/{attachment_id}",
        name="qledger_attachment",
        description="Original file bytes, authorized against the current user and parent paths on every read.",
        mime_type="application/octet-stream",
    )
    async def read_attachment(unit_id: str, attachment_id: str) -> bytes:
        # SDK resource callbacks consume bytes, not BlobResourceContents. The
        # download tool provides the specific MIME type and filename metadata.
        resource = await attachment_resource(unit_id, attachment_id)
        return base64.b64decode(resource.blob, validate=True)

    return server
