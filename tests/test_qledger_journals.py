import json
import unittest
from unittest.mock import patch
import httpx
from tests.qledger_support import U,E,R,A,client


def journal():
    return {'transaction_date':'2026-10-17','description':'Invoice','lines':[{'account_id':R,'debit':'12.123456'},{'account_id':A,'credit':'12.123456'}]}


class QledgerJournalTests(unittest.IsolatedAsyncioTestCase):
    async def test_transaction_mapping_and_stale_review(self):
        from quollnet_mcp.qledger.tools import journals as t
        from quollnet_mcp.qledger.models_accounting import JournalCreate, JournalPatch, PostRequest, ReversalRequest
        seen=[]
        conflict=False
        def handler(req):
            seen.append(req)
            return httpx.Response(409,json={'message':'Evidence changed'}) if conflict else httpx.Response(200,json={'id':E,'status':'draft','version':3,'reviewed_evidence':{'records':{R:2},'attachments':{A:'digest'}}})
        async with client(handler) as c:
            with patch.object(t,'qledger_client',c), patch('quollnet_mcp.qledger.tools.common.auth.unit_token',return_value='unit'):
                post=PostRequest(version=3,reviewed_evidence={'records':{R:2},'attachments':{A:'digest'}})
                cases=[
                    (lambda:t.list_qledger_transactions(U),'GET','',False),
                    (lambda:t.get_qledger_transaction(U,E),'GET','/'+E,False),
                    (lambda:t.create_qledger_transaction(U,JournalCreate(**journal()),'k'),'POST','',True),
                    (lambda:t.update_qledger_transaction(U,E,JournalPatch(version=3,description='Changed')),'PATCH','/'+E,False),
                    (lambda:t.post_qledger_transaction(U,E,post),'POST','/'+E+'/post',False),
                    (lambda:t.reverse_qledger_transaction(U,E,ReversalRequest(transaction_date='2026-10-17',description='Reverse'),'k'),'POST','/'+E+'/reverse',True),
                    (lambda:t.delete_qledger_transaction(U,E),'DELETE','/'+E,False),
                ]
                for fn,method,suffix,keyed in cases:
                    result=await fn()
                    self.assertEqual((seen[-1].method,seen[-1].url.path),(method,'/api/units/'+U+'/journal-entries'+suffix))
                    self.assertEqual('Idempotency-Key' in seen[-1].headers,keyed)
                    self.assertEqual(result['reviewed_evidence']['records'],{R:2})
                self.assertEqual(json.loads(seen[2].content)['lines'][0]['debit'],'12.123456')
                self.assertEqual(json.loads(seen[3].content),{'version':3,'description':'Changed'})
                self.assertEqual(seen[6].content,b'')
                conflict=True
                before=len(seen)
                with self.assertRaisesRegex(Exception,'409.*review'):
                    await t.post_qledger_transaction(U,E,post)
                self.assertEqual(len(seen),before+1)
                self.assertEqual(json.loads(seen[-1].content)['reviewed_evidence'],{'records':{R:2},'attachments':{A:'digest'}})
