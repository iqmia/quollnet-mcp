import unittest

from app import app, server_status


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


if __name__ == "__main__":
    unittest.main()
