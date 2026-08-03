import os

from mcp.server import MCPServer
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route


SERVICE_NAME = os.getenv("QUOLLNET_SERVICE", "quollnet-mcp")
SERVICE_VERSION = os.getenv("QUOLLNET_VERSION", "0.1.0")

mcp = MCPServer(
    SERVICE_NAME,
    version=SERVICE_VERSION,
)


@mcp.tool()
async def server_status() -> dict[str, str]:
    """Return the current service status."""
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "ok",
    }

mcp_http_app = mcp.streamable_http_app(
    json_response=True,
    stateless_http=True,
)

async def health(_: Request) -> JSONResponse:
    return JSONResponse(await server_status())


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Mount("/mcp", app=mcp.streamable_http_app()),
    ]
)
