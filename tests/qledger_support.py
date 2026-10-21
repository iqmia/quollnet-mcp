import os
from dataclasses import replace
import httpx

os.environ.setdefault("QAUTH_APP_ID", "test-app-id")
os.environ.setdefault("QAUTH_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("QAPP_APP_ID", "qapp-test-app")
os.environ.setdefault("CASHFLOWPOT_APP_ID", "cashflowpot-test-app")

U = "11111111-1111-4111-8111-111111111111"
E = "22222222-2222-4222-8222-222222222222"
R = "33333333-3333-4333-8333-333333333333"
A = "44444444-4444-4444-8444-444444444444"
L = "55555555-5555-4555-8555-555555555555"


def settings():
    from quollnet_mcp.config import get_settings

    return replace(
        get_settings(),
        qledger_enabled=True,
        qledger_app_id="ledger-app",
        qledger_base_url="https://ledger.test",
    )


def client(handler):
    from quollnet_mcp.qledger.qledger_client import QledgerClient

    result = QledgerClient(settings())
    result._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://ledger.test",
        follow_redirects=False,
    )
    return result
