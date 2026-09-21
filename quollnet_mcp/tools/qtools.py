from typing import Annotated, Any, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.services.qapp_client import QAppClientError


class QToolHowToStepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: Annotated[int, Field(ge=1, le=50)]
    name: Annotated[str, Field(min_length=1, max_length=250)]
    text: Annotated[str, Field(min_length=1, max_length=2000)]


class QToolMetadataInput(BaseModel):
    """Editable database metadata for a Quollnet qTool."""

    model_config = ConfigDict(extra="forbid")

    description: Annotated[str | None, Field(max_length=2000)] = None
    embed_description: Annotated[str | None, Field(max_length=1000)] = None
    seo_title: Annotated[str | None, Field(max_length=255)] = None
    seo_description: Annotated[str | None, Field(max_length=2000)] = None
    keywords: Annotated[str | None, Field(max_length=2000)] = None
    hero_image: Annotated[str | None, Field(max_length=255)] = None
    application_category: Annotated[str | None, Field(max_length=80)] = None
    operating_system: Annotated[str | None, Field(max_length=40)] = None
    login_required: bool | None = None
    article_embed_allowed: bool | None = None
    changefreq: Annotated[str | None, Field(max_length=20)] = None
    sitemap_priority: Annotated[str | None, Field(max_length=10)] = None
    howto_name: Annotated[str | None, Field(max_length=255)] = None
    howto_description: Annotated[str | None, Field(max_length=2000)] = None
    howto_steps: list[QToolHowToStepInput] | None = None


def _access_token(required_scope: str):
    access_token = get_access_token()
    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    scopes = set(access_token.scopes or [])
    if required_scope not in scopes:
        raise ToolError(
            f"The connected account does not have {required_scope} permission"
        )

    return access_token


async def get_qtool_generation_spec() -> dict[str, Any]:
    """Retrieve the authoritative qTools V2 package-generation specification.

    Use this before creating or substantially modifying a qTool package. qApp
    performs deterministic validation when the working package is saved.
    """
    access_token = _access_token("qtools:read")

    try:
        return await qapp_client.get_qtool_generation_spec(
            access_token=access_token.token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def list_qtools(
    page: Annotated[int, Field(ge=1)] = 1,
    per_page: Annotated[int, Field(ge=1, le=100)] = 25,
    status: Literal["saved", "published", "disabled"] | None = None,
) -> dict[str, Any]:
    """List qTools accessible to the authenticated creator.

    qApp admins receive all qTools. Normal users receive only qTools they
    created. Use this before creating a tool when an existing slug may already
    be present.
    """
    access_token = _access_token("qtools:read")

    try:
        return await qapp_client.list_qtools(
            access_token=access_token.token,
            page=page,
            per_page=per_page,
            status=status,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def get_qtool(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
) -> dict[str, Any]:
    """Get qTool metadata, lifecycle state, URLs, and version information."""
    access_token = _access_token("qtools:read")

    try:
        return await qapp_client.get_qtool(
            access_token=access_token.token,
            slug=slug,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def create_qtool(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
            description="Unique lowercase kebab-case qTool URL slug.",
        ),
    ],
    tool_name: Annotated[str, Field(min_length=1, max_length=160)],
    metadata: QToolMetadataInput | None = None,
) -> dict[str, Any]:
    """Create a new qTool with mutable working version v1.

    Retrieve get_qtool_generation_spec first. This call creates metadata and
    returns the working preview URL; package files are added separately.
    """
    access_token = _access_token("qtools:create")

    payload: dict[str, Any] = {
        "slug": slug,
        "tool_name": tool_name,
    }
    if metadata is not None:
        payload["metadata"] = metadata.model_dump(exclude_none=True)

    try:
        return await qapp_client.create_qtool(
            access_token=access_token.token,
            payload=payload,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def update_qtool_metadata(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
    tool_name: Annotated[str | None, Field(min_length=1, max_length=160)] = None,
    metadata: QToolMetadataInput | None = None,
) -> dict[str, Any]:
    """Update editable qTool metadata without changing package version history."""
    access_token = _access_token("qtools:edit")

    payload: dict[str, Any] = {}
    if tool_name is not None:
        payload["tool_name"] = tool_name
    if metadata is not None:
        payload.update(metadata.model_dump(exclude_unset=True))

    if not payload:
        raise ToolError("No qTool metadata changes were provided")

    try:
        return await qapp_client.update_qtool_metadata(
            access_token=access_token.token,
            slug=slug,
            payload=payload,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def list_qtool_files(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
) -> dict[str, Any]:
    """List files in the current working package or latest saved package."""
    access_token = _access_token("qtools:read")

    try:
        return await qapp_client.list_qtool_files(
            access_token=access_token.token,
            slug=slug,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def get_qtool_file(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
    path: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description=(
                "Package-relative path such as core.html, css/tool.css, "
                "js/app.js, or assets/example.png."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Read one qTool package file.

    Text files are returned as UTF-8. Binary files are returned as base64.
    """
    access_token = _access_token("qtools:read")

    try:
        return await qapp_client.get_qtool_file(
            access_token=access_token.token,
            slug=slug,
            relative_path=path,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def write_qtool_file(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
    path: Annotated[str, Field(min_length=1, max_length=500)],
    content: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "Complete file content. For base64 encoding, provide raw base64 "
                "without a data-URI prefix."
            ),
        ),
    ],
    encoding: Literal["utf-8", "base64"] = "utf-8",
) -> dict[str, Any]:
    """Create or replace one file in the current working qTool package.

    If the latest version is already saved, qApp automatically creates the next
    working version once and clones the saved package before applying the edit.
    Repeated edits then remain on that same working version until Save.
    """
    access_token = _access_token("qtools:edit")

    try:
        return await qapp_client.write_qtool_file(
            access_token=access_token.token,
            slug=slug,
            relative_path=path,
            payload={
                "encoding": encoding,
                "content": content,
            },
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def delete_qtool_file(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
    path: Annotated[str, Field(min_length=1, max_length=500)],
) -> dict[str, Any]:
    """Delete one file from the current working qTool package."""
    access_token = _access_token("qtools:edit")

    try:
        return await qapp_client.delete_qtool_file(
            access_token=access_token.token,
            slug=slug,
            relative_path=path,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def save_qtool(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
) -> dict[str, Any]:
    """Validate and save the current working qTool version.

    Validation errors are returned from qApp so the working package can be
    repaired and saved again without creating version spam.
    """
    access_token = _access_token("qtools:edit")

    try:
        return await qapp_client.save_qtool(
            access_token=access_token.token,
            slug=slug,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def publish_qtool(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
    version: Annotated[int | None, Field(ge=1)] = None,
) -> dict[str, Any]:
    """Publish a retained saved qTool version.

    qApp requires both qtools:publish permission and an admin app role. If
    version is omitted, qApp publishes the latest saved version.
    """
    access_token = _access_token("qtools:publish")

    try:
        return await qapp_client.publish_qtool(
            access_token=access_token.token,
            slug=slug,
            version=version,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def disable_qtool(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
) -> dict[str, Any]:
    """Disable a qTool. qApp restricts this operation to app admins."""
    access_token = _access_token("qtools:publish")

    try:
        return await qapp_client.disable_qtool(
            access_token=access_token.token,
            slug=slug,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def set_qtool_indexing(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        ),
    ],
    indexed: bool,
) -> dict[str, Any]:
    """Set qTool discoverability. qApp restricts this operation to app admins.

    Indexing is independent of publication, but it is only effective publicly
    while the tool status is published.
    """
    access_token = _access_token("qtools:publish")

    try:
        return await qapp_client.set_qtool_indexing(
            access_token=access_token.token,
            slug=slug,
            indexed=indexed,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error
