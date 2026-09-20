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

from quollnet_mcp.dependencies import qapp_client, qauth_client, qflow_client
from quollnet_mcp.auth import QAuthTokenVerifier
from quollnet_mcp.config import get_settings
from quollnet_mcp.tools.cashflowpot import (
    create_cashflow,
    list_cashflow_projects,
)
from quollnet_mcp.tools.articles import (
    create_article_draft,
    edit_article_draft,
    get_article,
    get_internal_link_candidates,
    list_article_files,
    rename_article_file,
    replace_article_body_text,
    search_articles,
    get_article_authoring_policy,
    set_article_hero_image,
    upload_article_file,
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
        required_scopes=["quollnet:access"],
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
        "securitySchemes": [{"type": "oauth2", "scopes": ["quollnet:access", "articles:read"]}],
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
                "scopes": ["quollnet:access", "articles:read"],
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
                "scopes": ["quollnet:access", "articles:read"],
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
                "scopes": ["quollnet:access", "articles:create"],
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
                "scopes": ["quollnet:access", "articles:read"],
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
                "scopes": ["quollnet:access", "articles:edit"],
            }
        ],
        "openai/toolInvocation/invoking": "Updating article draft",
        "openai/toolInvocation/invoked": "Article draft updated",
    },
)(edit_article_draft)


mcp.tool(
    name="replace_article_body_text",
    title="Replace text in Quollnet article draft",
    description=(
        "Make a localized edit to an unpublished Quollnet article draft without "
        "resending the full article body. The old_text must match exactly once. "
        "Use the smallest unique exact fragment that safely identifies the edit "
        "location. old_text may be the content being changed or a unique anchor "
        "used to insert content before or after it. To insert after an anchor, "
        "include the original anchor followed by the new HTML in new_text. To "
        "insert before an anchor, place the new HTML before the original anchor. "
        "When using an anchor only as an insertion point, preserve that anchor "
        "exactly in new_text. For formatting changes, replace the complete HTML "
        "element being restyled. Use this tool for small wording changes, local "
        "section additions, formatting changes, URL substitutions, and download "
        "placeholder replacement. Use edit_article_draft for substantial rewrites "
        "or changes that must also update authoring metadata."
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
                "scopes": ["quollnet:access", "articles:edit"],
            }
        ],
        "openai/toolInvocation/invoking": "Updating article text",
        "openai/toolInvocation/invoked": "Article text updated",
    },
)(replace_article_body_text)


mcp.tool(
    name="upload_article_file",
    title="Upload Quollnet article file",
    description=(
        "Upload a file to a Quollnet article's file folder. Images are converted to "
        "WebP by qApp by default; set convert_to_webp=false when the original image "
        "format must be preserved. The returned filename and URL are authoritative "
        "because image conversion may change the filename extension. Use "
        "list_article_files afterwards when file discovery is needed."
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
                "scopes": ["quollnet:access", "articles:files:create"],
            }
        ],
        "openai/toolInvocation/invoking": "Uploading article file",
        "openai/toolInvocation/invoked": "Article file uploaded",
    },
)(upload_article_file)


mcp.tool(
    name="list_article_files",
    title="List Quollnet article files",
    description=(
        "List files stored for a Quollnet article, including each file's exact stored "
        "filename, permanent URL, and whether it is an image. Use this before referring "
        "to, renaming, embedding, or linking an existing article file. For requests "
        "such as 'insert file X after section B', first use this tool to resolve the "
        "actual stored filename and URL, then use replace_article_body_text to insert "
        "the appropriate HTML at a unique article-body anchor."
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
                "scopes": ["quollnet:access", "articles:files:list"],
            }
        ],
        "openai/toolInvocation/invoking": "Retrieving article files",
        "openai/toolInvocation/invoked": "Article files retrieved",
    },
)(list_article_files)


mcp.tool(
    name="rename_article_file",
    title="Rename Quollnet article file",
    description=(
        "Rename an existing file in a Quollnet article folder, typically to improve "
        "clarity or SEO. Use list_article_files first to obtain the exact current "
        "filename. qApp automatically updates exact permanent-file URL references in "
        "the article body, including download links and embedded images, and updates "
        "the hero URL when applicable. Do not manually patch those file URLs after a "
        "successful rename unless the user also requested surrounding content changes."
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
                "scopes": ["quollnet:access", "articles:files:update"],
            }
        ],
        "openai/toolInvocation/invoking": "Renaming article file",
        "openai/toolInvocation/invoked": "Article file renamed",
    },
)(rename_article_file)


mcp.tool(
    name="set_article_hero_image",
    title="Set Quollnet article hero image",
    description=(
        "Assign an existing article file as the hero image for a Quollnet article. "
        "The file must already exist in that article's file folder; use "
        "list_article_files first when the exact stored filename is not already known. "
        "This only assigns the hero image and does not insert the image into the "
        "article body. Do not use replace_article_body_text for hero image assignment."
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
                "scopes": ["quollnet:access", "articles:files:update"],
            }
        ],
        "openai/toolInvocation/invoking": "Setting article hero image",
        "openai/toolInvocation/invoked": "Article hero image updated",
    },
)(set_article_hero_image)


mcp.tool(
    name="list_cashflow_projects",
    title="List CashflowPot projects",
    description=(
        "List the authenticated user's CashflowPot projects (QAuth Units) and "
        "their existing cashflow scenarios. Use the returned project id as the "
        "unit_id for CashflowPot creation tools."
    ),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    ),
    meta={
        "securitySchemes": [
            {"type": "oauth2", "scopes": ["quollnet:access"]}
        ],
        "openai/toolInvocation/invoking": "Retrieving CashflowPot projects",
        "openai/toolInvocation/invoked": "CashflowPot projects retrieved",
    },
)(list_cashflow_projects)


mcp.tool(
    name="create_cashflow",
    title="Create CashflowPot scenario",
    description=(
        "Create and calculate a CashflowPot scenario in an existing project. "
        "Provide project commercial assumptions and activities using the "
        "CashflowPot portable input model. Percentages are fractions (0.10 = 10%). "
        "q_flow validates the inputs and remains authoritative for all calculated "
        "cashflow series and KPIs."
    ),
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        open_world_hint=False,
    ),
    meta={
        "securitySchemes": [
            {"type": "oauth2", "scopes": ["quollnet:access"]}
        ],
        "openai/toolInvocation/invoking": "Creating CashflowPot scenario",
        "openai/toolInvocation/invoked": "CashflowPot scenario created",
    },
)(create_cashflow)


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
        async with qauth_client:
            async with qflow_client:
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

