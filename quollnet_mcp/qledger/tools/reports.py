from uuid import UUID
from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger.models import LedgerQuery
from .common import call, unit_path, object_id


async def get_qledger_ledger(unit_id: UUID, query: LedgerQuery = LedgerQuery()):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/ledger",
        unit_id=unit_id,
        query=query,
    )


async def get_qledger_account_statement(
    unit_id: UUID, account_id: UUID, query: LedgerQuery = LedgerQuery()
):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/accounts/" + object_id(account_id) + "/statement",
        unit_id=unit_id,
        query=query,
    )


async def get_qledger_partner_statement(
    unit_id: UUID, account_id: UUID, query: LedgerQuery = LedgerQuery()
):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id)
        + "/accounts/"
        + object_id(account_id)
        + "/partner-statement",
        unit_id=unit_id,
        query=query,
    )


async def get_qledger_trial_balance(unit_id: UUID, query: LedgerQuery = LedgerQuery()):
    return await call(
        qledger_client,
        "GET",
        unit_path(unit_id) + "/trial-balance",
        unit_id=unit_id,
        query=query,
    )
