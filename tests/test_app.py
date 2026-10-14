import os
import unittest

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

from app import app, mcp, server_status


class AppTests(unittest.IsolatedAsyncioTestCase):
    async def test_imported_asgi_app(self) -> None:
        self.assertTrue(callable(app))

    async def test_server_status(self) -> None:
        self.assertEqual(
            await server_status(),
            {
                "service": "quollnet-mcp",
                "version": "0.1.0",
                "status": "ok",
            },
        )

    async def test_server_advertises_qarticles_workflow_instructions(self) -> None:
        instructions = mcp.instructions or ""

        self.assertIn("qApp is authoritative", instructions)
        self.assertIn("get_article_authoring_policy", instructions)
        self.assertIn("preserve its existing slug", instructions)
        self.assertIn("recheck_article", instructions)
        self.assertIn("validate_article_for_publish", instructions)
        self.assertIn("Never hard-delete", instructions)


if __name__ == "__main__":
    unittest.main()
