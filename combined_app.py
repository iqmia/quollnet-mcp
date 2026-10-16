"""Combined ASGI entrypoint for the existing Quollnet and dedicated CashflowPot MCPs.

The legacy ``app.py`` remains unchanged so its /mcp behavior and compatibility
tools stay intact. Production should run ``combined_app:app`` to expose both MCP
resources from one process and one shared backend-client pool.
"""

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from mcp.server.transport_security import TransportSecuritySettings

import app as legacy
from quollnet_mcp.cashflowpot.server import build_cashflowpot_server
from quollnet_mcp.dependencies import qapp_client, qauth_client, qflow_client


settings = legacy.settings
cashflowpot_mcp = build_cashflowpot_server(settings)
_cashflowpot_http_app = cashflowpot_mcp.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["mcp.quollnet.com", "mcp.quollnet.com:*"],
        allowed_origins=["https://chatgpt.com"],
    ),
)


class CanonicalCashflowPotPathMiddleware:
    """Internally normalize the exact resource URI without an HTTP redirect.

    Starlette ``Mount('/cashflowpot', ...)`` dispatches subpaths such as
    ``/cashflowpot/`` but does not dispatch the exact no-trailing-slash path.
    QAuth and MCP deliberately use the canonical resource URI
    ``https://mcp.quollnet.com/cashflowpot``. Rewriting only the ASGI routing
    path keeps that public URI exact while letting the mounted MCP app receive
    its expected inner ``/`` path.
    """

    def __init__(self, application) -> None:
        self.application = application

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") in {"http", "websocket"} and scope.get("path") == "/cashflowpot":
            scope = dict(scope)
            scope["path"] = "/cashflowpot/"
            scope["raw_path"] = b"/cashflowpot/"
        await self.application(scope, receive, send)


@asynccontextmanager
async def lifespan(_: Starlette) -> AsyncGenerator[None, None]:
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(qapp_client)
        await stack.enter_async_context(qauth_client)
        await stack.enter_async_context(qflow_client)
        await stack.enter_async_context(legacy.mcp.session_manager.run())
        await stack.enter_async_context(cashflowpot_mcp.session_manager.run())
        yield


app = Starlette(
    routes=[
        Route("/health", legacy.health, methods=["GET"]),
        Mount("/cashflowpot", app=_cashflowpot_http_app),
        Mount("/", app=legacy.mcp_http_app),
    ],
    lifespan=lifespan,
)
app.add_middleware(CanonicalCashflowPotPathMiddleware)
