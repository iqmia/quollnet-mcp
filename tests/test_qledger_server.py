import os
import unittest
from dataclasses import replace
from unittest.mock import patch
import httpx
from tests.qledger_support import settings


class QledgerServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_registration_and_schemas(self):
        from quollnet_mcp.qledger.server import build_qledger_server
        from app import mcp
        from combined_app import cashflowpot_mcp

        server = build_qledger_server(settings())
        tools = await server.list_tools()
        names = {t.name for t in tools}
        self.assertEqual(len(names), 49)
        for required in [
            "execute_qledger_operation",
            "post_qledger_transaction",
            "unpost_qledger_record",
            "download_qledger_attachment",
            "invite_qledger_member",
        ]:
            self.assertIn(required, names)
        self.assertFalse(names & {t.name for t in await mcp.list_tools()})
        self.assertFalse(names & {t.name for t in await cashflowpot_mcp.list_tools()})
        for t in tools:
            self.assertIn("securitySchemes", t.meta)
            if t.name not in ["list_qledger_units", "create_qledger_unit"]:
                self.assertIn("unit_id", t.input_schema["required"])
        post = next(t for t in tools if t.name == "post_qledger_transaction")
        self.assertTrue(post.annotations.destructive_hint)
        self.assertFalse(post.annotations.read_only_hint)
        get = next(t for t in tools if t.name == "get_qledger_record")
        self.assertTrue(get.annotations.read_only_hint)
        templates = await server.list_resource_templates()
        self.assertEqual(len(templates), 1)

    async def test_canonical_path_and_discovery(self):
        from combined_app import build_combined_app

        application = build_combined_app(settings())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="https://mcp.quollnet.com",
            follow_redirects=False,
        ) as c:
            for path in ["/qledger", "/qledger/"]:
                r = await c.post(
                    path,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {},
                    },
                )
                self.assertEqual(r.status_code, 401)
                self.assertIsNone(r.headers.get("location"))
                self.assertIn(
                    "/.well-known/oauth-protected-resource/qledger",
                    r.headers["www-authenticate"],
                )
            r = await c.get("/.well-known/oauth-protected-resource/qledger")
            self.assertEqual(r.json()["resource"], "https://mcp.quollnet.com/qledger")
            self.assertEqual(
                r.json()["authorization_servers"], ["https://quollnet.com/api"]
            )
            r = await c.get("/.well-known/oauth-protected-resource/cashflowpot")
            self.assertEqual(
                r.json()["resource"], "https://mcp.quollnet.com/cashflowpot"
            )
        disabled = build_combined_app(
            replace(
                settings(),
                qledger_enabled=False,
                qledger_app_id="",
                qledger_base_url="",
            )
        )
        self.assertIsNone(disabled.state.qledger_mcp)
        self.assertNotIn("/qledger", [r.path for r in disabled.routes])

    def test_disabled_endpoint_ignores_its_invalid_optional_settings(self):
        from quollnet_mcp.config import get_settings

        with patch.dict(
            os.environ,
            {
                "QLEDGER_ENABLED": "false",
                "QLEDGER_MAX_FILE_BYTES": "unused",
                "QLEDGER_TIMEOUT_SECONDS": "unused",
            },
        ):
            self.assertFalse(get_settings().qledger_enabled)

    def test_optional_config_validation(self):
        from quollnet_mcp.config import get_settings

        with patch.dict(
            os.environ,
            {"QLEDGER_ENABLED": "false", "QLEDGER_APP_ID": "", "QLEDGER_BASE_URL": ""},
        ):
            self.assertFalse(get_settings().qledger_enabled)
        with patch.dict(
            os.environ,
            {"QLEDGER_ENABLED": "true", "QLEDGER_APP_ID": "", "QLEDGER_BASE_URL": ""},
        ):
            with self.assertRaises(ValueError):
                get_settings()
