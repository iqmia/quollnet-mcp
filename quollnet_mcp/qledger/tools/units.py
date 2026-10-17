from uuid import UUID
from urllib.parse import quote
from quollnet_mcp.dependencies import qledger_client
from quollnet_mcp.qledger.models import UnitCreate, MemberInvite, MemberRoles, PageQuery
from .common import call, unit_path, object_id


_UNIT_FIELDS = {'id','name','description','color','parent_unit_id','is_active','created_at','updated_at'}


def _unit(value):
    return {k:v for k,v in value.items() if k in _UNIT_FIELDS and isinstance(v, (str, int, float, bool, type(None)))} if isinstance(value,dict) else None


async def list_qledger_units(query: PageQuery = PageQuery()):
    return await call(qledger_client,'GET','/api/units',query=query)


async def create_qledger_unit(request: UnitCreate):
    result = await call(qledger_client,'POST','/api/units',body=request)
    return {'unit':_unit(result['unit'])}


async def load_qledger_unit(unit_id: UUID):
    result = await call(qledger_client,'POST',unit_path(unit_id)+'/load')
    return {'unit':_unit(result['unit']),'parent':_unit(result.get('parent')),
            'children_page':[_unit(u) for u in result.get('children_page',[])]}


async def list_qledger_members(unit_id: UUID, query: PageQuery = PageQuery()):
    return await call(qledger_client,'GET',unit_path(unit_id)+'/members',unit_id=unit_id,query=query)


async def invite_qledger_member(unit_id: UUID, request: MemberInvite):
    return await call(qledger_client,'POST',unit_path(unit_id)+'/members/invite',unit_id=unit_id,body=request)


async def remove_qledger_member(unit_id: UUID, user_id: UUID):
    return await call(qledger_client,'DELETE',unit_path(unit_id)+'/members/'+object_id(user_id),unit_id=unit_id)


async def list_qledger_roles(unit_id: UUID):
    return await call(qledger_client,'GET',unit_path(unit_id)+'/roles',unit_id=unit_id)


async def add_qledger_member_roles(unit_id: UUID, user_id: UUID, request: MemberRoles):
    return await call(qledger_client,'POST',unit_path(unit_id)+'/members/'+object_id(user_id)+'/roles',unit_id=unit_id,body=request)


async def remove_qledger_member_role(unit_id: UUID, user_id: UUID, role_name: str):
    if not role_name or len(role_name) > 100 or role_name in ('.','..'):
        raise ValueError('Invalid role name')
    return await call(qledger_client,'DELETE',unit_path(unit_id)+'/members/'+object_id(user_id)+'/roles/'+quote(role_name,safe=''),unit_id=unit_id)
