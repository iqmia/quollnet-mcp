from uuid import UUID
from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger.models_accounting import SettingsCreate, SettingsPatch
from .common import call, unit_path


async def get_qledger_settings(unit_id: UUID):
    return await call(
        qledger_client, "GET", unit_path(unit_id) + "/settings", unit_id=unit_id
    )


async def initialize_qledger_settings(unit_id: UUID, request: SettingsCreate):
    return await call(
        qledger_client,
        "PUT",
        unit_path(unit_id) + "/settings",
        unit_id=unit_id,
        body=request,
    )


async def update_qledger_settings(unit_id: UUID, request: SettingsPatch):
    return await call(
        qledger_client,
        "PATCH",
        unit_path(unit_id) + "/settings",
        unit_id=unit_id,
        body=request,
    )
