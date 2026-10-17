from uuid import UUID
from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger.models import PageQuery
from quollnet_mcp.qledger.models_accounting import AccountCreate, AccountPatch
from .common import call, unit_path, object_id


async def list_qledger_accounts(unit_id: UUID, query: PageQuery = PageQuery()):
    return await call(qledger_client,'GET',unit_path(unit_id)+'/accounts',unit_id=unit_id,query=query)


async def get_qledger_account(unit_id: UUID, account_id: UUID):
    return await call(qledger_client,'GET',unit_path(unit_id)+'/accounts/'+object_id(account_id),unit_id=unit_id)


async def create_qledger_account(unit_id: UUID, request: AccountCreate):
    return await call(qledger_client,'POST',unit_path(unit_id)+'/accounts',unit_id=unit_id,body=request)


async def update_qledger_account(unit_id: UUID, account_id: UUID, request: AccountPatch):
    return await call(qledger_client,'PATCH',unit_path(unit_id)+'/accounts/'+object_id(account_id),unit_id=unit_id,body=request)
