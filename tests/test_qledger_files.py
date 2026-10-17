import base64
import unittest
from unittest.mock import patch
import httpx
from tests.qledger_support import U,A,client


class QledgerFileTests(unittest.IsolatedAsyncioTestCase):
    def test_strict_decode_and_bounds(self):
        from quollnet_mcp.qledger.files import decode_file
        from quollnet_mcp.qledger.models import FileInput
        f=FileInput(filename='invoice.pdf',content_type='application/pdf',file_base64='cGRm')
        self.assertEqual(decode_file(f,max_bytes=3),('invoice.pdf',b'pdf','application/pdf'))
        for bad in ['!!!','data:application/pdf;base64,cGRm','a','']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                decode_file(FileInput(filename='invoice.pdf',file_base64=bad),max_bytes=3)
        with self.assertRaises(ValueError): decode_file(f,max_bytes=2)
        for name in ['../invoice.pdf','a/b','a\\b','\r\nfile','.','..']:
            with self.assertRaises(ValueError): decode_file(FileInput(filename=name,file_base64='cGRm'),max_bytes=3)

    async def test_authenticated_uncached_resource_and_stream_limit(self):
        from quollnet_mcp.qledger import files
        from quollnet_mcp.qledger.qledger_client import QledgerClientError
        seen=[]
        denied=False
        def handler(req):
            seen.append(req)
            return httpx.Response(403,json={'message':'Not allowed'}) if denied else httpx.Response(200,content=b'pdf',headers={'content-type':'application/pdf'})
        async with client(handler) as c:
            with patch.object(files,'qledger_client',c), patch.object(files.auth,'unit_token',side_effect=['first','second','revoked']):
                one=await files.attachment_resource(U,A)
                two=await files.attachment_resource(U,A)
                self.assertEqual(one.blob,'cGRm')
                self.assertEqual(one.mime_type,'application/pdf')
                self.assertEqual(one.uri,f'qledger://units/{U}/attachments/{A}')
                self.assertEqual([r.headers['Authorization'] for r in seen],['Bearer first','Bearer second'])
                denied=True
                with self.assertRaises(Exception): await files.attachment_resource(U,A)
            denied=False
            with self.assertRaises(QledgerClientError):
                await c.download('/api/file',access_token='token',max_bytes=2)
