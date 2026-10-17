import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch
import httpx
from tests.qledger_support import U,E,client


class QledgerAccountingTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_settings_and_report_mapping(self):
        from quollnet_mcp.qledger.tools import accounts, settings, reports
        from quollnet_mcp.qledger.models import PageQuery, LedgerQuery
        from quollnet_mcp.qledger.models_accounting import AccountCreate, AccountPatch, SettingsCreate, SettingsPatch
        seen=[]
        authoritative={'total':203,'page':2,'per_page':50,'total_debit':'123.123456','items':[]}
        def handler(req):
            seen.append(req)
            return httpx.Response(200,json=authoritative)
        async with client(handler) as c:
            with ExitStack() as stack:
                for mod in [accounts,settings,reports]: stack.enter_context(patch.object(mod,'qledger_client',c))
                stack.enter_context(patch('quollnet_mcp.qledger.tools.common.auth.unit_token',return_value='unit'))
                cases=[
                    (lambda:accounts.list_qledger_accounts(U,PageQuery(page=2)), 'GET','/accounts'),
                    (lambda:accounts.get_qledger_account(U,E), 'GET','/accounts/'+E),
                    (lambda:accounts.create_qledger_account(U,AccountCreate(code='100',name='Cash',account_type='asset',normal_balance='debit')), 'POST','/accounts'),
                    (lambda:accounts.update_qledger_account(U,E,AccountPatch(version=2,is_active=False)), 'PATCH','/accounts/'+E),
                    (lambda:settings.get_qledger_settings(U), 'GET','/settings'),
                    (lambda:settings.initialize_qledger_settings(U,SettingsCreate(base_currency='USD')), 'PUT','/settings'),
                    (lambda:settings.update_qledger_settings(U,SettingsPatch(version=2,locked_until_date=None)), 'PATCH','/settings'),
                    (lambda:reports.get_qledger_ledger(U,LedgerQuery(page=2,date_from='2026-01-01')), 'GET','/ledger'),
                    (lambda:reports.get_qledger_account_statement(U,E), 'GET','/accounts/'+E+'/statement'),
                    (lambda:reports.get_qledger_partner_statement(U,E), 'GET','/accounts/'+E+'/partner-statement'),
                    (lambda:reports.get_qledger_trial_balance(U), 'GET','/trial-balance'),
                ]
                for fn,method,suffix in cases:
                    with self.subTest(suffix=suffix,method=method):
                        self.assertEqual(await fn(),authoritative)
                        self.assertEqual((seen[-1].method,seen[-1].url.path),(method,'/api/units/'+U+suffix))
                        self.assertEqual(seen[-1].headers['Authorization'],'Bearer unit')
                self.assertEqual(json.loads(seen[3].content),{'version':2,'is_active':False})
                self.assertEqual(json.loads(seen[6].content),{'version':2,'locked_until_date':None})
                self.assertEqual(seen[7].url.params['page'],'2')
                self.assertEqual(seen[7].url.params['date_from'],'2026-01-01')
