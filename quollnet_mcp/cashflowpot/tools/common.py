from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from quollnet_mcp.services.qflow_client import QFlowClientError
from quollnet_mcp.cashflowpot.responses import project_response


async def call_qflow(response_type: type, operation: Callable[[], Awaitable[Any]]) -> Any:
    try:
        result = await operation()
    except QFlowClientError as error:
        raise ToolError(str(error)) from error
    return project_response(result, response_type)


def require_permanent_confirmation(confirm_permanent: bool) -> None:
    if confirm_permanent is not True:
        raise ToolError(
            "Permanent deletion cannot be undone. Set confirm_permanent=true only "
            "after the user explicitly requests permanent deletion of this item."
        )
