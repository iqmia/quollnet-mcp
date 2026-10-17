from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.services.qflow_client import QFlowClientError


async def call_qflow(operation: Callable[[], Awaitable[Any]]) -> Any:
    try:
        return await operation()
    except QFlowClientError as error:
        raise ToolError(str(error)) from error
