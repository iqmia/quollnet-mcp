from typing import Annotated, Any, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.services.qapp_client import QAppClientError


async def search_articles(
    q: Annotated[str | None, Field(max_length=250)] = None,
    topic: Annotated[str | None, Field(max_length=100)] = None,
    lang: str | None = None,
    status: Literal["all", "published", "draft"] = "all",
    sort_by: Literal["modified", "published", "title"] = "modified",
    sort_dir: Literal["asc", "desc"] = "desc",
    page: Annotated[int, Field(ge=1)] = 1,
    per_page: Annotated[int, Field(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    """Search published articles and the authenticated user's drafts."""
    access_token = get_access_token()
    if access_token is None or not access_token.subject:
        raise ToolError("Authentication is required")

    try:
        return await qapp_client.search_articles(
            access_token=access_token.token,
            q=q,
            topic=topic,
            lang=lang,
            status=status,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            per_page=per_page,
        )
    except QAppClientError as error:
        raise ToolError("Article search failed") from error
