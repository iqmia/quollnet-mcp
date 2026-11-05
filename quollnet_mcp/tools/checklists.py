"""Checklist template authoring through the connected user's qChecklists API."""
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal
from urllib.parse import quote

import httpx
from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from quollnet_mcp.dependencies import qauth_client
from quollnet_mcp.qledger.files import download_file
from quollnet_mcp.qledger.models import FileInput
from quollnet_mcp.services.qauth_client import QAuthClientError


CHECKLISTS = "v1/checklists"
ATTACHMENTS = "v1/attachments"
MAX_CHECKLIST_FILE_BYTES = 20 * 1024 * 1024

# Generated images can arrive without a filename. The shared downloader uses
# "upload.bin" in that case, which qChecklists rejects as an unsupported type.
CHECKLIST_FILE_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}


def _upload_filename(name: str, content: bytes, mime: str) -> str:
    """Give unnamed ChatGPT files a supported extension and check common image signatures."""
    if mime == "image/png" and not content.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
        raise ToolError("Downloaded file does not contain a valid PNG header")
    if mime == "image/jpeg" and not content.startswith(b"\\xff\\xd8\\xff"):
        raise ToolError("Downloaded file does not contain a valid JPEG header")
    if mime == "image/webp" and not (
        content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    ):
        raise ToolError("Downloaded file does not contain a valid WebP header")
    if mime == "image/gif" and not content.startswith((b"GIF87a", b"GIF89a")):
        raise ToolError("Downloaded file does not contain a valid GIF header")
    if name == "upload.bin":
        extension = CHECKLIST_FILE_EXTENSIONS.get(mime)
        if extension is None:
            raise ToolError("ChatGPT did not provide a supported filename or file type")
        return f"chatgpt-upload.{extension}"
    return name
AttachmentId = Annotated[str, Field(min_length=1, max_length=50)]
ChecklistId = Annotated[str, Field(min_length=1, max_length=36)]
Revision = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$",
                                description="Exact revision returned by qChecklists.")]


class ChecklistMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    title: str | None = None
    h1: str | None = None
    introduction: str | None = None
    summary: list[str] | None = None
    paragraphs: list[dict[str, Any]] | None = None
    how_to_title: str | None = None
    how_to: list[dict[str, Any]] | None = Field(default=None, description="Guidance steps with a text field.")
    faq: list[dict[str, Any]] | None = None
    categories: list[str] | None = None
    meta_description: str | None = None
    meta_keywords: list[str] | None = None
    hero_image_alt: str | None = None
    main_image_prompt: str | None = Field(default=None, max_length=500,
        description="Visual prompt used to generate the checklist hero image; saved with the checklist.")
    call_to_action_title: str | None = None
    call_to_action_paragraph: str | None = None
    is_compact: bool | None = None


class ChecklistCreate(ChecklistMetadata):
    name: str = Field(min_length=1)
    categories: list[str]
    slug: str | None = None


class ChecklistItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    items_title: str | None = Field(default=None, description="Optional checklist section heading.")


class ChecklistItemAdd(ChecklistItemCreate):
    position: int | None = Field(default=None, ge=1, description="One-based insertion position. Omit to append.")


class ChecklistItemEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: ChecklistId
    text: str | None = Field(default=None, min_length=1)
    items_title: str | None = None


def _detail(checklist_id: str) -> str:
    return f"{CHECKLISTS}/{quote(checklist_id, safe='')}"


@asynccontextmanager
async def _checklists_client():
    access = get_access_token()
    if access is None or not access.subject:
        raise ToolError("Authentication is required")
    settings = qauth_client.settings
    try:
        token = await qauth_client.exchange_app_token(
            mcp_access_token=access.token, target_app_id=settings.qchecklists_app_id,
        )
    except QAuthClientError as error:
        raise ToolError(str(error)) from error
    async with httpx.AsyncClient(
        base_url=settings.qchecklists_base_url.rstrip("/") + "/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=settings.qchecklists_timeout_seconds,
    ) as client:
        yield client


async def _request(client, method, path, *, revision=None, **kwargs):
    headers = {"If-Match": f'"{revision}"'} if revision else None
    try:
        response = await client.request(method, path, headers=headers, **kwargs)
    except httpx.RequestError as error:
        raise ToolError("qChecklists could not be reached") from error
    try:
        result = response.json()
    except ValueError:
        result = None
    if not response.is_success:
        message = result.get("message") if isinstance(result, dict) else None
        raise ToolError(f"qChecklists HTTP {response.status_code}: {message or 'Request failed'}")
    if not isinstance(result, dict):
        raise ToolError("qChecklists returned an invalid response")
    return result


async def search_checklists(
    search: Annotated[str | None, Field(default=None, max_length=250)] = None,
    mine_only: bool = False,
    page: Annotated[int, Field(ge=1)] = 1,
    per_page: Annotated[int, Field(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    """Search accessible checklist templates. Use get_checklist for complete items and guidance."""
    params = {"my": mine_only, "page": page, "per_page": per_page}
    if search:
        params["search"] = search
    async with _checklists_client() as client:
        result = await _request(client, "GET", CHECKLISTS, params=params)
    compact_fields = ("id", "slug", "name", "title", "meta_description", "categories",
                      "is_public", "is_posted", "created_by", "revision")
    result["data"] = [{key: row[key] for key in compact_fields if key in row}
                      for row in result["data"]]
    return result


async def get_checklist(checklist_id: ChecklistId | None = None,
                        slug: Annotated[str | None, Field(max_length=100)] = None) -> dict[str, Any]:
    """Retrieve a full checklist template by ID or slug, including item IDs and its revision."""
    if bool(checklist_id) == bool(slug):
        raise ToolError("Supply exactly one checklist ID or slug")
    path = _detail(checklist_id) if checklist_id else f"{CHECKLISTS}/slug/{quote(slug, safe='')}"
    async with _checklists_client() as client:
        return await _request(client, "GET", path)


async def create_checklist(metadata: ChecklistCreate,
                           items: Annotated[list[ChecklistItemCreate], Field(min_length=1)]) -> dict[str, Any]:
    """Create a private, unpublished checklist draft with ordered items."""
    payload = metadata.model_dump(exclude_unset=True)
    if "title" not in payload:
        payload["title"] = metadata.name
    payload.update(is_public=False, editorial_draft=True)
    payload["items"] = [
        {**item.model_dump(exclude_none=True), "position": position}
        for position, item in enumerate(items, 1)
    ]
    async with _checklists_client() as client:
        return await _request(client, "POST", CHECKLISTS, json=payload)


async def update_checklist(checklist_id: ChecklistId, expected_revision: Revision,
                           changes: ChecklistMetadata) -> dict[str, Any]:
    """Update only the supplied checklist metadata fields. Editing requires an unpublished checklist."""
    payload = changes.model_dump(exclude_unset=True)
    if not payload:
        raise ToolError("Provide at least one metadata change")
    async with _checklists_client() as client:
        return await _request(client, "PATCH", _detail(checklist_id),
                              revision=expected_revision, json=payload)


def _edited_items(items, add, edit, delete_item_ids, item_order):
    by_id = {
        item["id"]: {key: item[key] for key in ("id", "text", "items_title") if key in item}
        for item in sorted(items, key=lambda item: (item["position"], item["id"]))
    }
    edit_ids = [item.item_id for item in edit]
    if len(set(edit_ids)) != len(edit_ids) or len(set(delete_item_ids)) != len(delete_item_ids):
        raise ToolError("Each item may be edited or deleted only once per request")
    if set(edit_ids) & set(delete_item_ids):
        raise ToolError("An item cannot be edited and deleted in the same request")
    if (set(edit_ids) | set(delete_item_ids)) - by_id.keys():
        raise ToolError("Every edited or deleted item ID must belong to the checklist")
    for change in edit:
        fields = change.model_dump(exclude_unset=True, exclude={"item_id"})
        if not fields or ("text" in fields and fields["text"] is None):
            raise ToolError("Each item edit needs new text or a section-heading change")
        by_id[change.item_id].update(fields)
    for item_id in delete_item_ids:
        del by_id[item_id]
    if item_order is not None:
        if len(item_order) != len(by_id) or set(item_order) != set(by_id):
            raise ToolError("item_order must list all retained item IDs exactly once")
        result = [by_id[item_id] for item_id in item_order]
    else:
        result = list(by_id.values())
    for item in add:
        position = item.position if item.position is not None else len(result) + 1
        if position > len(result) + 1:
            raise ToolError("A new item's position cannot exceed the current list length plus one")
        result.insert(position - 1, item.model_dump(exclude={"position"}, exclude_none=True))
    if not result:
        raise ToolError("A checklist must contain at least one item")
    return [{**item, "position": position} for position, item in enumerate(result, 1)]


async def edit_checklist_items(
    checklist_id: ChecklistId, expected_revision: Revision,
    add: list[ChecklistItemAdd] | None = None,
    edit: list[ChecklistItemEdit] | None = None,
    delete_item_ids: list[ChecklistId] | None = None,
    item_order: list[ChecklistId] | None = None,
) -> dict[str, Any]:
    """Edit draft items in one save. Order retained IDs first, then insert new items in input order."""
    if not (add or edit or delete_item_ids or item_order is not None):
        raise ToolError("Provide at least one item change")
    path = _detail(checklist_id)
    async with _checklists_client() as client:
        current = (await _request(client, "GET", path))["data"]
        if current["revision"] != expected_revision:
            raise ToolError("The checklist has changed. Reload it and retry with its current revision.")
        items = _edited_items(current["items"], add or [], edit or [], delete_item_ids or [], item_order)
        return await _request(client, "PUT", f"{path}/items", revision=expected_revision,
                              json={"items": items})


async def validate_checklist(checklist_id: ChecklistId) -> dict[str, Any]:
    """Get qChecklists' publication validation result and the exact validated revision."""
    async with _checklists_client() as client:
        return await _request(client, "GET", f"{_detail(checklist_id)}/validate")


async def publish_checklist(checklist_id: ChecklistId, expected_revision: Revision,
                            visibility: Literal["public", "private"]) -> dict[str, Any]:
    """Publish the revision returned by validate_checklist and refresh its PDF, Excel and preview."""
    async with _checklists_client() as client:
        return await _request(client, "POST", f"{_detail(checklist_id)}/publish",
                              revision=expected_revision, json={"visibility": visibility})


async def unpublish_checklist(checklist_id: ChecklistId, expected_revision: Revision) -> dict[str, Any]:
    """Withdraw an owned checklist and its public download links, leaving a private draft."""
    async with _checklists_client() as client:
        return await _request(client, "POST", f"{_detail(checklist_id)}/unpublish",
                              revision=expected_revision)


async def _editable_checklist(client, checklist_id: str, expected_revision: str) -> dict[str, Any]:
    checklist = (await _request(client, "GET", _detail(checklist_id)))["data"]
    if checklist["revision"] != expected_revision:
        raise ToolError("The checklist has changed. Reload it and retry with its current revision.")
    if checklist.get("is_posted"):
        raise ToolError("Unpublish the checklist before changing its files or image.")
    return checklist


async def _owned_attachment(client, checklist_id: str, attachment_id: str) -> dict[str, Any]:
    attachment = (await _request(
        client, "GET", f"{ATTACHMENTS}/{quote(attachment_id, safe='')}"
    ))["data"]
    if attachment.get("owner_type") != "checklist" or attachment.get("owner_id") != checklist_id:
        raise ToolError("Attachment does not belong to this checklist")
    return attachment


async def list_checklist_files(checklist_id: ChecklistId) -> dict[str, Any]:
    """List the checklist's uploaded attachments, including file IDs, names, and URLs."""
    async with _checklists_client() as client:
        return await _request(client, "GET", ATTACHMENTS,
                              params={"owner_type": "checklist", "owner_id": checklist_id})


async def add_checklist_file(
    checklist_id: ChecklistId, expected_revision: Revision, file: FileInput,
    document_type: Annotated[str | None, Field(max_length=50)] = None,
    alt_text: Annotated[str | None, Field(max_length=255)] = None,
    description: Annotated[str | None, Field(max_length=255)] = None,
) -> dict[str, Any]:
    """Upload an authorized ChatGPT file to an unpublished checklist. Use the returned attachment ID to assign hero or download CTA."""
    async with _checklists_client() as client:
        await _editable_checklist(client, checklist_id, expected_revision)
        try:
            name, contents, mime = await download_file(file, max_bytes=MAX_CHECKLIST_FILE_BYTES)
        except ValueError as error:
            raise ToolError(str(error)) from None
        name = _upload_filename(name, contents, mime)
        fields = {"owner_type": "checklist", "owner_id": checklist_id}
        if document_type is not None:
            fields["document_type"] = document_type
        if alt_text is not None:
            fields["alt_text"] = alt_text
        if description is not None:
            fields["description"] = description
        return await _request(client, "POST", ATTACHMENTS,
                              data=fields, files={"file": (name, contents, mime)})


async def set_checklist_hero(
    checklist_id: ChecklistId, expected_revision: Revision, attachment_id: AttachmentId,
    alt_text: Annotated[str | None, Field(max_length=500)] = None,
) -> dict[str, Any]:
    """Set an existing uploaded checklist image as the hero; the file stays in attachments."""
    async with _checklists_client() as client:
        await _editable_checklist(client, checklist_id, expected_revision)
        attachment = await _owned_attachment(client, checklist_id, attachment_id)
        name = attachment["file_name"]
        mime = (attachment.get("file_type") or "").lower()
        if not (mime.startswith("image/") or name.lower().endswith((".webp", ".png", ".jpg", ".jpeg", ".gif"))):
            raise ToolError("The hero attachment must be an image")
        return await _request(client, "PATCH", _detail(checklist_id),
                              revision=expected_revision, json={
                                  "hero_image": name,
                                  "hero_image_alt": alt_text if alt_text is not None else (attachment.get("alt_text") or ""),
                              })


async def set_checklist_cta(
    checklist_id: ChecklistId, expected_revision: Revision, attachment_id: AttachmentId,
    text: Annotated[str | None, Field(max_length=255)] = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Add/update a download CTA for an uploaded file, or remove that file's CTA. Preserves all other download links."""
    async with _checklists_client() as client:
        checklist = await _editable_checklist(client, checklist_id, expected_revision)
        attachment = await _owned_attachment(client, checklist_id, attachment_id)
        url = attachment["file_url"]
        links = [
            link for link in (checklist.get("call_to_action_urls") or [])
            if link.get("attachment_id") != attachment_id and link.get("url") != url
        ]
        if enabled:
            label = (text or "").strip()
            if not label:
                raise ToolError("Provide a download button label when enabling a CTA")
            links.append({"text": label, "url": url, "attachment_id": attachment_id})
        return await _request(client, "PATCH", _detail(checklist_id),
                              revision=expected_revision, json={"call_to_action_urls": links})


async def remove_checklist_file(
    checklist_id: ChecklistId, expected_revision: Revision, attachment_id: AttachmentId,
) -> dict[str, Any]:
    """Delete an uploaded checklist file, clearing its hero and download CTA references first."""
    async with _checklists_client() as client:
        checklist = await _editable_checklist(client, checklist_id, expected_revision)
        attachment = await _owned_attachment(client, checklist_id, attachment_id)
        changes = {}
        if checklist.get("hero_image") == attachment["file_name"]:
            changes.update(hero_image=None, hero_image_alt=None)
        links = checklist.get("call_to_action_urls") or []
        kept = [
            link for link in links
            if link.get("attachment_id") != attachment_id
            and link.get("url") != attachment.get("file_url")
        ]
        if len(kept) != len(links):
            changes["call_to_action_urls"] = kept
        if changes:
            await _request(client, "PATCH", _detail(checklist_id),
                           revision=expected_revision, json=changes)
        return await _request(client, "DELETE",
                              f"{ATTACHMENTS}/{quote(attachment_id, safe='')}")


def register_checklist_tools(mcp: MCPServer) -> None:
    tools = (
        (search_checklists, True, False),
        (get_checklist, True, False),
        (create_checklist, False, False),
        (update_checklist, False, False),
        (edit_checklist_items, False, True),
        (list_checklist_files, True, False),
        (add_checklist_file, False, False),
        (remove_checklist_file, False, True),
        (set_checklist_hero, False, False),
        (set_checklist_cta, False, False),
        (validate_checklist, True, False),
        (publish_checklist, False, True),
        (unpublish_checklist, False, True),
    )
    for tool, read_only, destructive in tools:
        mcp.tool(
            name=tool.__name__,
            annotations=ToolAnnotations(read_only_hint=read_only,
                                        destructive_hint=destructive,
                                        open_world_hint=tool in (publish_checklist, unpublish_checklist)),
            meta={
                **({"openai/fileParams": ["file"]} if tool is add_checklist_file else {}),
                "securitySchemes": [{"type": "oauth2", "scopes": ["mcp:connect"]}],
            },
        )(tool)
