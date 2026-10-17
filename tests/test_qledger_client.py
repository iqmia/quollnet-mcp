import asyncio
import contextvars
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from tests.qledger_support import U, client, settings


class QledgerClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_mapping_and_errors(self):
        from quollnet_mcp.qledger.qledger_client import QledgerClientError

        seen = []

        def handler(req):
            seen.append(req)
            if req.url.path.endswith("/fail"):
                raise httpx.ReadTimeout("secret-token", request=req)
            if req.url.path.endswith("/conflict"):
                return httpx.Response(
                    409,
                    json={
                        "message": "Evidence changed",
                        "detail": {"code": "stale", "token": "secret-token"},
                    },
                )
            if req.url.path.endswith("/forbidden"):
                return httpx.Response(
                    403,
                    json={"message": "Permission required: journal:post secret-token"},
                )
            return httpx.Response(204)

        async with client(handler) as c:
            await c.request(
                "DELETE",
                "/api/units/" + U,
                access_token="secret-token",
                idempotency_key="same-key",
            )
            self.assertEqual(seen[-1].headers["Authorization"], "Bearer secret-token")
            self.assertEqual(seen[-1].headers["Idempotency-Key"], "same-key")
            for path in ["/conflict", "/forbidden"]:
                with self.assertRaises(QledgerClientError) as caught:
                    await c.request("POST", "/api" + path, access_token="secret-token")
                self.assertNotIn("secret-token", str(caught.exception))
                self.assertIn(
                    str(409 if path == "/conflict" else 403), str(caught.exception)
                )
            before = len(seen)
            with self.assertRaises(QledgerClientError) as caught:
                await c.request(
                    "POST",
                    "/api/fail",
                    access_token="secret-token",
                    idempotency_key="same-key",
                )
            self.assertTrue(caught.exception.outcome_unknown)
            self.assertIn("same", str(caught.exception))
            self.assertEqual(len(seen), before + 1)
            with self.assertRaises(ValueError):
                await c.request(
                    "GET", "https://evil.test/api", access_token="secret-token"
                )

    async def test_exchange_scope_and_concurrency(self):
        from quollnet_mcp.qledger import auth

        identity = contextvars.ContextVar("test_identity")
        seen = []

        async def exchange(**kwargs):
            seen.append(kwargs)
            await asyncio.sleep(0)
            return kwargs["mcp_access_token"] + ":" + str(kwargs["unit_id"])

        qauth = SimpleNamespace(settings=settings(), exchange_app_token=exchange)

        async def run(user, unit):
            identity.set(SimpleNamespace(token=user, subject=user))
            return await auth.unit_token(unit)

        with (
            patch.object(
                auth, "get_access_token", side_effect=lambda: identity.get(None)
            ),
            patch.object(auth, "qauth_client", qauth),
        ):
            result = await asyncio.gather(
                run("one", U), run("two", "22222222-2222-4222-8222-222222222222")
            )
            self.assertEqual(
                result, ["one:" + U, "two:22222222-2222-4222-8222-222222222222"]
            )
            identity.set(SimpleNamespace(token="app-user", subject="app-user"))
            await auth.application_token()
            self.assertIsNone(seen[-1]["unit_id"])
            self.assertEqual(seen[-1]["target_app_id"], "ledger-app")
            identity.set(None)
            with self.assertRaisesRegex(Exception, "Authentication"):
                await auth.application_token()

    async def test_json_and_multipart_contract(self):
        seen = []

        def handler(req):
            seen.append(req)
            return httpx.Response(201, json={"id": "ok"})

        async with client(handler) as c:
            self.assertEqual(
                await c.request(
                    "GET",
                    "/api/test",
                    access_token="token",
                    params={"page": 1, "date_from": None},
                ),
                {"id": "ok"},
            )
            self.assertEqual(str(seen[-1].url), "https://ledger.test/api/test?page=1")
            await c.multipart(
                "/api/test",
                access_token="token",
                fields={"payload": "{}"},
                files={"invoice": ("invoice.pdf", b"pdf", "application/pdf")},
                idempotency_key="k",
            )
            self.assertIn(b'name="invoice"', seen[-1].content)
            self.assertEqual(seen[-1].headers["Idempotency-Key"], "k")

    async def test_validation_errors_preserve_fields_without_input_or_credentials(self):
        from quollnet_mcp.qledger.qledger_client import QledgerClientError

        def handler(req):
            return httpx.Response(
                422,
                json={
                    "message": "Validation error",
                    "detail": {
                        "json": {"lines.0.account_id": ["Invalid UUID"]},
                        "token": "secret-token",
                        "input": {"password": "secret"},
                    },
                },
            )

        async with client(handler) as c:
            with self.assertRaises(QledgerClientError) as caught:
                await c.request("POST", "/api/test", access_token="secret-token")
            self.assertIn("lines.0.account_id", str(caught.exception))
            self.assertIn("Invalid UUID", str(caught.exception))
            self.assertNotIn("secret", str(caught.exception))

    async def test_error_download_is_bounded_too(self):
        from quollnet_mcp.qledger.qledger_client import QledgerClientError

        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self):
                for _ in range(100):
                    yield b"x" * 100

        def handler(req):
            return httpx.Response(500, stream=Stream())

        async with client(handler) as c:
            with self.assertRaisesRegex(QledgerClientError, "limit"):
                await c.download("/api/test", access_token="token", max_bytes=10)

    async def test_mutation_bad_response_does_not_imply_no_side_effect(self):
        from quollnet_mcp.qledger.qledger_client import QledgerClientError

        for status, body in [(201, b"not json"), (503, b"upstream unavailable")]:

            def handler(req):
                return httpx.Response(status, content=body)

            async with client(handler) as c:
                with self.assertRaises(QledgerClientError) as caught:
                    await c.request(
                        "POST",
                        "/api/test",
                        access_token="token",
                        idempotency_key="existing-key",
                    )
                self.assertTrue(caught.exception.outcome_unknown)
                self.assertIn("same idempotency key", str(caught.exception))
