from typing import Annotated, Any, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.services.qapp_client import QAppClientError


_QTOOL_SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class QToolHowToStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: Annotated[int, Field(ge=1, le=50)]
    name: Annotated[str, Field(min_length=1, max_length=250)]
    text: Annotated[str, Field(min_length=1, max_length=2000)]


class QToolMetadataUpdate(BaseModel):
    """Approved mutable metadata for an existing qTool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: Annotated[str | None, Field(max_length=160)] = None
    description: Annotated[str | None, Field(max_length=2000)] = None
    embed_description: Annotated[str | None, Field(max_length=1000)] = None
    seo_title: Annotated[str | None, Field(max_length=255)] = None
    seo_description: Annotated[str | None, Field(max_length=2000)] = None
    keywords: Annotated[str | None, Field(max_length=2000)] = None
    application_category: Annotated[str | None, Field(max_length=80)] = None
    operating_system: Annotated[str | None, Field(max_length=40)] = None
    login_required: bool | None = None
    article_embed_allowed: bool | None = None
    changefreq: Literal["daily", "weekly", "monthly", "yearly", "never"] | None = None
    sitemap_priority: Annotated[str | None, Field(max_length=10)] = None
    howto_name: Annotated[str | None, Field(max_length=255)] = None
    howto_description: Annotated[str | None, Field(max_length=2000)] = None
    howto_steps: list[QToolHowToStep] | None = None


def _require_scope(scope: str):
    access_token = get_access_token()

    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    scopes = set(access_token.scopes or [])
    if scope not in scopes:
        raise ToolError(
            f"The connected account does not have {scope} permission"
        )

    return access_token


async def get_qtool_development_guide() -> dict[str, Any]:
    """Return the canonical Quollnet Tools V2 development guide."""
    access_token = _require_scope("qtools:read")

    try:
        return await qapp_client.get_qtool_development_guide(
            access_token=access_token.token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def list_qtools(
    status: Literal["saved", "published", "disabled"] | None = None,
    page: Annotated[int, Field(ge=1)] = 1,
    per_page: Annotated[int, Field(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    """List qTools visible to the connected user."""
    access_token = _require_scope("qtools:read")

    try:
        return await qapp_client.list_qtools(
            access_token=access_token.token,
            status=status,
            page=page,
            per_page=per_page,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def get_qtool(
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=_QTOOL_SLUG,
            description="Canonical lowercase kebab-case qTool slug.",
        ),
    ],
) -> dict[str, Any]:
    """Inspect one qTool, its versions, and the current editable package file list."""
    access_token = _require_scope("qtools:read")

    try:
        tool_response = await qapp_client.get_qtool(
            access_token=access_token.token,
            slug=slug,
        )
        files_response = await qapp_client.list_qtool_files(
            access_token=access_token.token,
            slug=slug,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error

    tool_data = tool_response.get("data", {})
    package_data = files_response.get("data", {})

    if isinstance(tool_data, dict):
        combined = dict(tool_data)
        combined["package"] = package_data
        return {"data": combined}

    return {
        "data": {
            "tool": tool_data,
            "package": package_data,
        }
    }


async def get_qtool_file(
    slug: Annotated[
        str,
        Field(min_length=1, max_length=80, pattern=_QTOOL_SLUG),
    ],
    relative_path: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description=(
                "Package-relative file path returned by get_qtool, "
                "for example core.html, css/01-base.css, or js/01-ui.js."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Read one file from the qTool package selected for the next edit."""
    access_token = _require_scope("qtools:read")

    try:
        return await qapp_client.get_qtool_file(
            access_token=access_token.token,
            slug=slug,
            relative_path=relative_path,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def update_qtool_file(
    slug: Annotated[
        str,
        Field(min_length=1, max_length=80, pattern=_QTOOL_SLUG),
    ],
    relative_path: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description=(
                "Package-relative file path. Editing a saved tool causes qApp "
                "to create/clone the next mutable working version."
            ),
        ),
    ],
    content: Annotated[
        str,
        Field(
            description=(
                "Complete replacement file content. Use UTF-8 text for HTML, "
                "CSS, JavaScript, JSON, TXT, or CSV; use base64 only for "
                "supported binary package assets."
            )
        ),
    ],
    encoding: Literal["utf-8", "base64"] = "utf-8",
) -> dict[str, Any]:
    """Replace one qTool package file in the mutable working version."""
    access_token = _require_scope("qtools:edit")

    try:
        return await qapp_client.update_qtool_file(
            access_token=access_token.token,
            slug=slug,
            relative_path=relative_path,
            content=content,
            encoding=encoding,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def update_qtool_metadata(
    slug: Annotated[
        str,
        Field(min_length=1, max_length=80, pattern=_QTOOL_SLUG),
    ],
    metadata: QToolMetadataUpdate,
) -> dict[str, Any]:
    """Update selected metadata for an existing qTool without publishing it."""
    access_token = _require_scope("qtools:edit")
    payload = metadata.model_dump(exclude_unset=True)

    if not payload:
        raise ToolError("At least one metadata field must be supplied")

    try:
        return await qapp_client.update_qtool_metadata(
            access_token=access_token.token,
            slug=slug,
            payload=payload,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error
