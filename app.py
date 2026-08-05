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
    search_articles,
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

# Define the create_article_draft tool, which allows authenticated users to create
# new article drafts in the Quollnet system. This tool requires the "articles:create"
# scope for authorization.
mcp.tool(
    name="create_article_draft",
    title="Create Quollnet article draft",
    description=(
        "Create a new unpublished Quollnet article draft owned by the "
        "authenticated user. The draft is validated by qApp and cannot "
        "be published or assigned to another user through this tool."
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
