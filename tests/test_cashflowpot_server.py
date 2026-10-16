import os
import time
import unittest

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from quollnet_mcp.auth import QAuthTokenVerifier
from quollnet_mcp.config import get_settings


class CashflowPotResourceConfigTests(unittest.TestCase):
    def test_cashflowpot_resource_uri_defaults_independently(self) -> None:
        settings = get_settings()
        self.assertEqual(settings.mcp_resource_uri, "https://mcp.quollnet.com/mcp")
        self.assertEqual(
            settings.cashflowpot_mcp_resource_uri,
            "https://mcp.quollnet.com/cashflowpot",
        )


class CashflowPotAudienceIsolationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cls.public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def _token(self, audience: str) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "iss": "https://quollnet.com/api",
                "sub": "user-1",
                "user_id": "user-1",
                "aud": audience,
                "scope": "mcp:connect",
                "token_use": "mcp_access",
                "client_app_id": "test-app-id",
                "iat": now,
                "nbf": now - 1,
                "exp": now + 600,
            },
            self.private_pem,
            algorithm="RS256",
            headers={"kid": "test-app-id", "typ": "JWT"},
        )

    async def test_each_resource_accepts_only_its_exact_audience(self) -> None:
        central = QAuthTokenVerifier(
            issuer_url="https://quollnet.com/api",
            resource_uri="https://mcp.quollnet.com/mcp",
            app_id="test-app-id",
            public_key=self.public_pem,
        )
        cashflowpot = QAuthTokenVerifier(
            issuer_url="https://quollnet.com/api",
            resource_uri="https://mcp.quollnet.com/cashflowpot",
            app_id="test-app-id",
            public_key=self.public_pem,
        )
        central_token = self._token("https://mcp.quollnet.com/mcp")
        cashflowpot_token = self._token("https://mcp.quollnet.com/cashflowpot")

        self.assertIsNotNone(await central.verify_token(central_token))
        self.assertIsNone(await central.verify_token(cashflowpot_token))
        self.assertIsNotNone(await cashflowpot.verify_token(cashflowpot_token))
        self.assertIsNone(await cashflowpot.verify_token(central_token))


class CashflowPotMountTests(unittest.TestCase):
    def test_combined_app_mounts_dedicated_resource_before_existing_catch_all(self) -> None:
        from combined_app import app, cashflowpot_mcp
        from app import mcp

        self.assertIsNot(cashflowpot_mcp, mcp)
        mounts = [
            route.path
            for route in app.routes
            if route.__class__.__name__ == "Mount"
        ]
        self.assertIn("/cashflowpot", mounts)
        self.assertTrue("" in mounts or "/" in mounts)
        central_path = "" if "" in mounts else "/"
        self.assertLess(mounts.index("/cashflowpot"), mounts.index(central_path))

    def test_dedicated_server_has_cashflowpot_instructions_only(self) -> None:
        from combined_app import cashflowpot_mcp

        instructions = cashflowpot_mcp.instructions or ""
        self.assertIn("q_flow is authoritative", instructions)
        self.assertIn("periods are zero-based", instructions)
        self.assertNotIn("QArticles", instructions)


if __name__ == "__main__":
    unittest.main()
