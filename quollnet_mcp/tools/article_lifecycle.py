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
    state.
    """
    access_token = await qapp_user_token()
    encoded_id = urllib.parse.quote(article_id, safe="")
    try:
        return await qapp_client.get_json(
            f"/articles/api/v1/articles/{encoded_id}/validate",
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


async def recheck_article(
    article_id: Annotated[str, _ARTICLE_ID],
) -> dict[str, Any]:
    """Run qApp's deterministic article health checks after editing."""
    access_token = await qapp_user_token()
    encoded_id = urllib.parse.quote(article_id, safe="")
    try:
        return await qapp_client.get_json(
            f"/articles/api/v1/articles/{encoded_id}/recheck",
            access_token=access_token,
        )
    except QAppClientError as error:
        raise ToolError(str(error)) from error


def register_article_lifecycle_tools(mcp: MCPServer) -> None:
    """Register QArticles health/reference tools on the MCP server."""
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
        title="Validate Quollnet article for publication",
        description=(
            "Run qApp's authoritative publication-readiness validation for one "
            "article. Use this before publish_article once that lifecycle tool is "
            "available."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Validating article",
            "openai/toolInvocation/invoked": "Article validation complete",
        },
    )(validate_article_for_publish)

    mcp.tool(
        name="recheck_article",
        title="Recheck Quollnet article",
        description=(
            "Run qApp's deterministic article health checks after editing and "
            "return structured errors, warnings, and check results."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            open_world_hint=False,
        ),
        meta={
            "securitySchemes": security,
            "openai/toolInvocation/invoking": "Rechecking article",
            "openai/toolInvocation/invoked": "Article recheck complete",
        },
    )(recheck_article)
