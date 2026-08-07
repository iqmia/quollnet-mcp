import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from quollnet_mcp.dependencies import qapp_client
from quollnet_mcp.auth import QAuthTokenVerifier
from quollnet_mcp.config import get_settings
from quollnet_mcp.tools.articles import (
    create_article_draft,
    edit_article_draft,
    get_article,
    get_internal_link_candidates,
    search_articles,
    get_article_authoring_policy,
)
from mcp.server.transport_security import TransportSecuritySettings


SERVICE_NAME = os.getenv("QUOLLNET_SERVICE", "quollnet-mcp")
SERVICE_VERSION = os.getenv("QUOLLNET_VERSION", "0.1.0")
settings = get_settings()

mcp = MCPServer(
    SERVICE_NAME,
    version=SERVICE_VERSION,
    token_verifier=QAuthTokenVerifier(
        issuer_url=settings.qauth_issuer_url,
        resource_uri=settings.mcp_resource_uri,
        app_id=settings.qauth_app_id,
        public_key=settings.qauth_public_key,
    ),
    auth=AuthSettings(
        issuer_url=settings.qauth_issuer_url,
        resource_server_url=settings.mcp_resource_uri,
        required_scopes=["articles:read"],
    ),
)

# Define a function to return the current service status, including the service 
# name, version, and status.
async def server_status() -> dict[str, str]:
    """Return the current service status."""
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "ok",
    }

# Define the search_articles and create_article_draft tools, which are used to 
# interact with the Quollnet article system.
mcp.tool(
    name="search_articles",
    title="Search Quollnet articles",
    description=(
        "Search existing published articles and the authenticated user's drafts; "
        "returns compact metadata and pagination, not article bodies."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
    meta={
        "securitySchemes": [{"type": "oauth2", "scopes": ["articles:read"]}],
        "openai/toolInvocation/invoking": "Searching articles",
        "openai/toolInvocation/invoked": "Article search complete",
    },
)(search_articles)


# Define the get_article_authoring_policy tool, which retrieves the current
# authoritative Quollnet article-authoring policy from qApp. This tool requires the
# "articles:read" scope for authorization.
mcp.tool(
    name="get_article_authoring_policy",
    title="Get Quollnet article-authoring policy",
    description=(
        "Retrieve the current authoritative Quollnet article-authoring "
        "policy from qApp. Use it before preparing or creating an article "
        "draft."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
    meta={
        "securitySchemes": [
            {
                "type": "oauth2",
                "scopes": ["articles:read"],
            }
        ],
        "openai/toolInvocation/invoking": "Retrieving article policy",
        "openai/toolInvocation/invoked": "Article policy retrieved",
    },
)(get_article_authoring_policy)


mcp.tool(
    name="get_internal_link_candidates",
    title="Get Quollnet internal-link candidates",
    description=(
        "Find ranked Quollnet internal-link candidates for a substantially completed "
        "article. Returns related articles, checklists associated with those articles, "
        "and related Method Statement/ITP candidates. Review the candidates and use "
        "only links that genuinely help the reader; do not insert all returned links "
        "automatically."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
    meta={
        "securitySchemes": [
            {
                "type": "oauth2",
                "scopes": ["articles:read"],
            }
        ],
        "openai/toolInvocation/invoking": "Finding related Quollnet content",
        "openai/toolInvocation/invoked": "Related content found",
    },
)(get_internal_link_candidates)


# Define the create_article_draft tool, which allows authenticated users to create
# new article drafts in the Quollnet system. This tool requires the "articles:create"
# scope for authorization.
mcp.tool(
    name="create_article_draft",
    title="Create Quollnet article draft",
    description=(
        "Create an unpublished Quollnet article draft for the authenticated "
        "user. Retrieve and follow the current article-authoring policy before "
        "calling this tool. The tool cannot publish an article or assign "
        "another owner."
    ),
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        open_world_hint=False,
    ),
    meta={
        "securitySchemes": [
            {
                "type": "oauth2",
                "scopes": ["articles:create"],
            }
        ],
        "openai/toolInvocation/invoking": "Creating article draft",
        "openai/toolInvocation/invoked": "Article draft created",
    },
)(create_article_draft)


mcp.tool(
    name="get_article",
    title="Get Quollnet article",
    description=(
        "Retrieve the full content and editable metadata for a Quollnet article by "
        "ID. Use search_articles first when the article ID is not already known."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
    meta={
        "securitySchemes": [
            {
                "type": "oauth2",
                "scopes": ["articles:read"],
            }
        ],
        "openai/toolInvocation/invoking": "Retrieving article",
        "openai/toolInvocation/invoked": "Article retrieved",
    },
)(get_article)


mcp.tool(
    name="edit_article_draft",
    title="Edit Quollnet article draft",
    description=(
        "Edit selected fields of an existing unpublished Quollnet article draft. "
        "Retrieve the draft first when reviewing or substantially revising existing "
        "content. qApp performs authoritative validation and will reject edits to "
        "published articles."
    ),
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        open_world_hint=False,
    ),
    meta={
        "securitySchemes": [
            {
                "type": "oauth2",
                "scopes": ["articles:edit"],
            }
        ],
        "openai/toolInvocation/invoking": "Updating article draft",
        "openai/toolInvocation/invoked": "Article draft updated",
    },
)(edit_article_draft)


# Define a health check endpoint that returns the current service status in JSON format.
async def health(_: Request) -> JSONResponse:
    return JSONResponse(await server_status())


# Define the ASGI application for the MCP server, including the health check endpoint
# and the MCP server routes. The application is configured with transport security settings
mcp_http_app = mcp.streamable_http_app(
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "mcp.quollnet.com",
            "mcp.quollnet.com:*",
        ],
        allowed_origins=[
            "https://chatgpt.com",
        ],
    ),
)

# Define the lifespan context manager for the ASGI application, which ensures that
# the qApp client and MCP session manager are properly initialized and closed during
# the application's lifetime.
@asynccontextmanager
async def lifespan(_: Starlette) -> AsyncGenerator[None, None]:
    async with qapp_client:
        async with mcp.session_manager.run():
            yield

# Define the ASGI application with the health check endpoint and the MCP server routes.
app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Mount("/", app=mcp_http_app),
    ],
    lifespan=lifespan,
)

