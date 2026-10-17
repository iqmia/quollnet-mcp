import unittest
from pydantic import ValidationError


class QledgerModelsTests(unittest.TestCase):
    def test_decimal_transport(self):
        from quollnet_mcp.qledger.models import api_payload
        from quollnet_mcp.qledger.models_accounting import LineCreate
        value = LineCreate(account_id='11111111-1111-4111-8111-111111111111', debit='12345678901234.123456')
        self.assertEqual(api_payload(value)['debit'], '12345678901234.123456')
        self.assertEqual(LineCreate.model_json_schema()['properties']['debit']['type'], 'string')
        for bad in [1.1, 'NaN', '0.0000001', '123456789012345.123456']:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                LineCreate(account_id=value.account_id, debit=bad)
        fx = LineCreate(account_id=value.account_id, debit='2', currency='USD', foreign_amount='1', exchange_rate='1.1234567890')
        self.assertEqual(api_payload(fx)['exchange_rate'], '1.1234567890')

    def test_patch_null_vs_omitted(self):
        from quollnet_mcp.qledger.models import api_payload
        from quollnet_mcp.qledger.models_records import RecordPatch, RecordCreate
        from quollnet_mcp.qledger.models_accounting import SettingsPatch
        self.assertEqual(api_payload(RecordPatch(version=1), patch=True), {'version': 1})
        self.assertEqual(api_payload(RecordPatch(version=1, data=None), patch=True), {'version': 1, 'data': None})
        self.assertEqual(api_payload(SettingsPatch(version=1, locked_until_date=None), patch=True), {'version': 1, 'locked_until_date': None})
        with self.assertRaises(ValidationError):
            RecordPatch(version=1, surprise=True)
        self.assertIsNone(RecordCreate(type='invoice', data=None).data)
        with self.assertRaises(ValidationError):
            RecordCreate(type='invoice', data={'bad': float('inf')})

    def test_operation_references(self):
        from quollnet_mcp.qledger.models_records import OperationRef, OperationRequest
        for bad in [{'kind':'record'}, {'kind':'record','id':'a','key':'a'}]:
            with self.assertRaises(ValidationError): OperationRef(**bad)
        for bad in [
            {'post_journal':True},
            {'records':[{'key':'journal','type':'invoice','data':{}}]},
            {'attachments':[{'key':'a','file_field':'x'},{'key':'b','file_field':'x'}]},
            {'post_records':[{'kind':'attachment','id':'a'}]},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError): OperationRequest(**bad)

    def test_query_and_key_validation(self):
        from quollnet_mcp.qledger.models import PageQuery, DateQuery, validate_idempotency_key
        self.assertEqual(PageQuery().per_page, 50)
        for n in [0, 201]:
            with self.assertRaises(ValidationError): PageQuery(per_page=n)
        with self.assertRaises(ValidationError): DateQuery(date_from='2026-12-01', date_to='2026-01-01')
        for key in ['', ' ', 'a'*129, 'a\nb']:
            with self.assertRaises(ValueError): validate_idempotency_key(key)
