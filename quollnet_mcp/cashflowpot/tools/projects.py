from typing import Annotated

from quollnet_mcp.cashflowpot.parameters import ProjectId, ConfirmPermanent
from quollnet_mcp.cashflowpot.responses import MessageResponse, ProjectListResponse, ProjectResponse
from pydantic import Field

from quollnet_mcp.cashflowpot.auth import cashflowpot_token
from quollnet_mcp.cashflowpot.models import ProjectInput, ProjectUpdate
from quollnet_mcp.cashflowpot.tools.common import call_qflow, require_permanent_confirmation
from quollnet_mcp.dependencies import qflow_client


async def list_cashflow_projects(
    page: Annotated[int, Field(ge=1, description="One-based results page to retrieve.")] = 1,
    per_page: Annotated[int, Field(ge=1, le=100, description="Maximum projects per page, from 1 to 100.")] = 25,
) -> ProjectListResponse:
    """List CashflowPot projects available to the connected user."""
    token = await cashflowpot_token()
    return await call_qflow(ProjectListResponse, lambda: qflow_client.list_projects(
        access_token=token, page=page, per_page=per_page
    ))


async def get_cashflow_project(unit_id: ProjectId) -> ProjectResponse:
    """Get one project including its active cashflow scenarios."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ProjectResponse, lambda: qflow_client.get_project(
        access_token=token, unit_id=unit_id
    ))


async def create_cashflow_project(project: ProjectInput) -> ProjectResponse:
    """Create a CashflowPot project and its base scenario."""
    token = await cashflowpot_token()
    return await call_qflow(ProjectResponse, lambda: qflow_client.create_project(
        access_token=token, payload=project.model_dump(exclude_none=True)
    ))


async def update_cashflow_project(unit_id: ProjectId, project: ProjectUpdate) -> ProjectResponse:
    """Update project metadata."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ProjectResponse, lambda: qflow_client.update_project(
        access_token=token,
        unit_id=unit_id,
        payload=project.model_dump(exclude_unset=True),
    ))


async def delete_cashflow_project(unit_id: ProjectId) -> MessageResponse:
    """Soft-delete/deactivate a project."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(MessageResponse, lambda: qflow_client.delete_project(
        access_token=token, unit_id=unit_id
    ))


async def restore_cashflow_project(unit_id: ProjectId) -> MessageResponse:
    """Restore/reactivate a previously deleted project."""
    # A deactivated Unit may not mint a unit token, so restoration starts from
    # the normal CashflowPot app token and lets q_flow/QAuth authorize it.
    token = await cashflowpot_token()
    return await call_qflow(MessageResponse, lambda: qflow_client.restore_project(
        access_token=token, unit_id=unit_id
    ))


async def hard_delete_cashflow_project(
    unit_id: ProjectId, confirm_permanent: ConfirmPermanent = False,
) -> MessageResponse:
    """Permanently delete a CashflowPot project and its local scenarios."""
    require_permanent_confirmation(confirm_permanent)
    # Hard deletion is valid after soft deletion, when QAuth may no longer mint
    # a Unit token. Use the normal CashflowPot app token and let q_flow/QAuth
    # authorize deletion of the requested Unit, matching project restoration.
    token = await cashflowpot_token()
    return await call_qflow(MessageResponse, lambda: qflow_client.hard_delete_project(
        access_token=token, unit_id=unit_id
    ))
