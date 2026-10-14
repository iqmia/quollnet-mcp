import urllib.parse
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.services.qapp_client import QAppClientError
from quollnet_mcp.tools.qapp_auth import qapp_user_token


_ARTICLE_ID = Field(
    min_length=1,
    max_length=250,
    description="Quollnet article ID.",
)


def _encoded_article_id(article_id: str) -> str:
    return urllib.parse.quote(article_id, safe="")


async def list_article_topics() -> dict[str, Any]:
    """Return the current qApp registry of valid QArticle topics."""
    access_token = await qapp_user_token()
    try:
        return await qapp_client.get_json(
            "/articles/api/v1/article-topics",
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def validate_article_for_publish(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Validate one article against qApp's publication-readiness rules.

    qApp is authoritative. Hard errors make the article invalid; warnings are
    returned for editorial review but do not by themselves change publication
    state. This public check is also the MCP's health check after substantial
    edits so the public tool surface remains compact.
    """
    access_token = await qapp_user_token()
    try:
        return await qapp_client.get_json(
            f"/articles/api/v1/articles/{_encoded_article_id(article_id)}/validate",
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def recheck_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Run qApp's deterministic article health checks after editing.

    Kept as an internal callable for tests and future server-side workflows. It
    is intentionally not advertised as a separate MCP tool because the public
    validate_article_for_publish tool already exposes the same health contract
    needed by connected models.
    """
    access_token = await qapp_user_token()
    try:
        return await qapp_client.get_json(
            f"/articles/api/v1/articles/{_encoded_article_id(article_id)}/recheck",
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def publish_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Publish or request publication of a QArticle through qApp.

    The article must first pass qApp's authoritative publication validation.
    qApp then applies the connected user's normal role: an author may publish
    their own article, an admin may publish permitted articles, and a normal
    owner creates a publication request instead of publishing directly.
    """
    access_token = await qapp_user_token()
    try:
        validation = await qapp_client.get_json(
            f"/articles/api/v1/articles/{_encoded_article_id(article_id)}/validate",
            access_token=access_token,
        )
        validation_data = (
            validation.get("data") if isinstance(validation, dict) else None
        )
        if not isinstance(validation_data, dict) or validation_data.get("valid") is not True:
            raise ToolError(
                "Article is not ready for publication; use "
                "validate_article_for_publish to review the errors"
            )

        return await qapp_client.post_json(
            "/articles/api/v1/articles/publish",
            payload={"id": article_id},
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def unpublish_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Unpublish a QArticle through qApp's normal ownership/role rules."""
    access_token = await qapp_user_token()
    try:
        return await qapp_client.post_json(
            "/articles/api/v1/articles/unpublish",
            payload={"id": article_id},
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def archive_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Soft-delete an unpublished QArticle through qApp.

    This never hard-deletes article data. qApp rejects publication-state or
    permission combinations that are not allowed.
    """
    access_token = await qapp_user_token()
    try:
        return await qapp_client.delete_json(
            "/articles/api/v1/articles/delete",
            payload={"id": article_id},
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def restore_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Restore a soft-deleted QArticle through qApp."""
    access_token = await qapp_user_token()
    try:
        return await qapp_client.post_json(
            "/articles/api/v1/articles/restore",
            payload={"id": article_id},
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


def register_article_lifecycle_tools(mcp: MCPServer) -> None:
    """Register QArticles health, reference, and lifecycle tools."""
    security = [{"type": "oauth2", "scopes": ["mcp:connect"]}]

    mcp.tool(
        name="list_article_topics",
        title="List Quollnet article topics",
        description=(
            "Return the current qApp registry of valid primary/additional article "
            "topic slugs. Use this instead of inventing topic values."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Retrieving article topics",
            "openai/toolInvocation/invoked": "Article topics retrieved",
        },
    )(list_article_topics)

    mcp.tool(
        name="validate_article_for_publish",
        title="Check Quollnet article health and publication readiness",
        description=(
            "Run qApp's authoritative article health/publication-readiness checks "
            "for one article. Use after substantial edits and before publication "
            "to inspect hard errors and editorial warnings."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Checking article",
            "openai/toolInvocation/invoked": "Article check complete",
        },
    )(validate_article_for_publish)

    mcp.tool(
        name="publish_article",
        title="Publish or request publication of Quollnet article",
        description=(
            "Validate an article and then ask qApp to publish it. qApp applies "
            "the connected user's normal role: normal owners request publication, "
            "authors may directly publish their own articles, and admins may "
            "publish according to qApp permissions."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Publishing article",
            "openai/toolInvocation/invoked": "Article publication action complete",
        },
    )(publish_article)

    mcp.tool(
        name="unpublish_article",
        title="Unpublish Quollnet article",
        description=(
            "Remove an article from public publication through qApp. qApp permits "
            "the article owner or an authorized admin according to its normal rules."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Unpublishing article",
            "openai/toolInvocation/invoked": "Article unpublished",
        },
    )(unpublish_article)

    mcp.tool(
        name="archive_article",
        title="Archive Quollnet article",
        description=(
            "Soft-delete an unpublished article through qApp. This is reversible "
            "with restore_article and never performs a hard delete."
        ),
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Archiving article",
            "openai/toolInvocation/invoked": "Article archived",
        },
    )(archive_article)

    mcp.tool(
        name="restore_article",
        title="Restore Quollnet article",
        description="Restore a previously soft-deleted article through qApp.",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Restoring article",
            "openai/toolInvocation/invoked": "Article restored",
        },
    )(restore_article)
