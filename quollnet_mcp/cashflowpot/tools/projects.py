from typing import Annotated, Any

from pydantic import Field

from quollnet_mcp.cashflowpot.auth import cashflowpot_token
from quollnet_mcp.cashflowpot.models import ProjectInput, ProjectUpdate
from quollnet_mcp.cashflowpot.tools.common import call_qflow
from quollnet_mcp.dependencies import qflow_client


async def list_cashflow_projects(
    page: Annotated[int, Field(ge=1)] = 1,
    per_page: Annotated[int, Field(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    """List CashflowPot projects available to the connected user."""
    token = await cashflowpot_token()
    return await call_qflow(lambda: qflow_client.list_projects(
        access_token=token, page=page, per_page=per_page
    ))


async def get_cashflow_project(unit_id: str) -> dict[str, Any]:
    """Get one project including its active cashflow scenarios."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.get_project(
        access_token=token, unit_id=unit_id
    ))


async def create_cashflow_project(project: ProjectInput) -> dict[str, Any]:
    """Create a CashflowPot project and its base scenario."""
    token = await cashflowpot_token()
    return await call_qflow(lambda: qflow_client.create_project(
        access_token=token, payload=project.model_dump(exclude_none=True)
    ))


async def update_cashflow_project(unit_id: str, project: ProjectUpdate) -> dict[str, Any]:
    """Update project metadata."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.update_project(
        access_token=token,
        unit_id=unit_id,
        payload=project.model_dump(exclude_none=True),
    ))


async def delete_cashflow_project(unit_id: str) -> dict[str, Any]:
    """Soft-delete/deactivate a project."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.delete_project(
        access_token=token, unit_id=unit_id
    ))


async def restore_cashflow_project(unit_id: str) -> dict[str, Any]:
    """Restore/reactivate a previously deleted project."""
    # A deactivated Unit may not mint a unit token, so restoration starts from
    # the normal CashflowPot app token and lets q_flow/QAuth authorize it.
    token = await cashflowpot_token()
    return await call_qflow(lambda: qflow_client.restore_project(
        access_token=token, unit_id=unit_id
    ))


async def hard_delete_cashflow_project(unit_id: str) -> dict[str, Any]:
    """Permanently delete a CashflowPot project and its local scenarios."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(lambda: qflow_client.hard_delete_project(
        access_token=token, unit_id=unit_id
    ))
