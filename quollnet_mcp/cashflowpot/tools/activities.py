from quollnet_mcp.cashflowpot.parameters import ProjectId, CashflowId, ActivityId, ActivityIds, ConfirmPermanent
from quollnet_mcp.cashflowpot.responses import ActivityListResponse, ActivityResponse, ActivityTypesResponse
from quollnet_mcp.cashflowpot.auth import cashflowpot_token
from quollnet_mcp.cashflowpot.models import ActivityInput, ActivityUpdate
from quollnet_mcp.cashflowpot.tools.common import call_qflow, require_permanent_confirmation
from quollnet_mcp.dependencies import qflow_client


async def get_activity_types() -> ActivityTypesResponse:
    """List CashflowPot activity type presets."""
    token = await cashflowpot_token()
    return await call_qflow(ActivityTypesResponse, lambda: qflow_client.get_activity_types(access_token=token))


async def get_activity(unit_id: ProjectId, activity_id: ActivityId) -> ActivityResponse:
    """Get one active activity."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ActivityResponse, lambda: qflow_client.get_activity(
        access_token=token, activity_id=activity_id
    ))


async def list_deleted_activities(unit_id: ProjectId, cashflow_id: CashflowId) -> ActivityListResponse:
    """List soft-deleted activities in one cashflow."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ActivityListResponse, lambda: qflow_client.list_deleted_activities(
        access_token=token, cashflow_id=cashflow_id
    ))


async def create_activity(
    unit_id: ProjectId, cashflow_id: CashflowId, activity: ActivityInput
) -> ActivityResponse:
    """Create Work, Manual Work, or Scheduled Cost activity source data."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ActivityResponse, lambda: qflow_client.create_activity(
        access_token=token,
        cashflow_id=cashflow_id,
        payload=activity.model_dump(exclude_none=True),
    ))


async def update_activity(
    unit_id: ProjectId, activity_id: ActivityId, activity: ActivityUpdate
) -> ActivityResponse:
    """Update one activity; q_flow validates and recalculates the scenario."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ActivityResponse, lambda: qflow_client.update_activity(
        access_token=token,
        activity_id=activity_id,
        payload=activity.model_dump(exclude_unset=True),
    ))


async def delete_activity(unit_id: ProjectId, activity_id: ActivityId) -> ActivityResponse:
    """Soft-delete one activity."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ActivityResponse, lambda: qflow_client.delete_activity(
        access_token=token, activity_id=activity_id
    ))


async def restore_activity(unit_id: ProjectId, activity_id: ActivityId) -> ActivityResponse:
    """Restore one soft-deleted activity."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ActivityResponse, lambda: qflow_client.restore_activity(
        access_token=token, activity_id=activity_id
    ))


async def restore_activities(unit_id: ProjectId, activity_ids: ActivityIds) -> ActivityResponse:
    """Restore multiple activities by ID."""
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ActivityResponse, lambda: qflow_client.restore_activities(
        access_token=token, activity_ids=activity_ids
    ))


async def hard_delete_activity(
    unit_id: ProjectId, activity_id: ActivityId,
    confirm_permanent: ConfirmPermanent = False,
) -> ActivityResponse:
    """Permanently delete one activity."""
    require_permanent_confirmation(confirm_permanent)
    token = await cashflowpot_token(unit_id)
    return await call_qflow(ActivityResponse, lambda: qflow_client.hard_delete_activity(
        access_token=token, activity_id=activity_id
    ))
