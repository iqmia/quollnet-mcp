import json
import unittest
from unittest.mock import patch
from tests.qledger_support import U, E, client


class QledgerUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_unit_token_redaction_and_mapping(self):
        from quollnet_mcp.qledger.tools import units
        from quollnet_mcp.qledger.models import UnitCreate, MemberInvite, MemberRoles
        seen=[]
        def handler(req):
            seen.append(req)
            return __import__('httpx').Response(200,json={'unit':{'id':U,'name':'Company','token':'nested-secret'},'token':'top-secret','parent':None,'children_page':[]})
        async with client(handler) as c:
            with patch.object(units,'qledger_client',c), patch('quollnet_mcp.qledger.tools.common.auth.application_token',return_value='app'), patch('quollnet_mcp.qledger.tools.common.auth.unit_token',return_value='unit'):
                result=await units.create_qledger_unit(UnitCreate(name='Company'))
                self.assertEqual(result,{'unit':{'id':U,'name':'Company'}})
                result=await units.load_qledger_unit(U)
                self.assertNotIn('secret',json.dumps(result))
                calls=[
                    (lambda:units.list_qledger_units(), 'GET','/api/units'),
                    (lambda:units.list_qledger_members(U), 'GET',f'/api/units/{U}/members'),
                    (lambda:units.invite_qledger_member(U,MemberInvite(email='a@example.com',send_email=False)), 'POST',f'/api/units/{U}/members/invite'),
                    (lambda:units.remove_qledger_member(U,E), 'DELETE',f'/api/units/{U}/members/{E}'),
                    (lambda:units.list_qledger_roles(U), 'GET',f'/api/units/{U}/roles'),
                    (lambda:units.add_qledger_member_roles(U,E,MemberRoles(roles=['controller'])), 'POST',f'/api/units/{U}/members/{E}/roles'),
                    (lambda:units.remove_qledger_member_role(U,E,'role/with space'), 'DELETE',f'/api/units/{U}/members/{E}/roles/role/with space'),
                ]
                for fn,method,path in calls:
                    await fn()
                    self.assertEqual((seen[-1].method,seen[-1].url.path),(method,path))
                self.assertIn('role%2Fwith%20space',str(seen[-1].url))
                self.assertIs(json.loads(seen[4].content)['send_email'],False)
