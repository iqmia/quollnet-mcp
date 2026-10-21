from quollnet_mcp.services.qapp_extended_client import QAppExtendedClient
from quollnet_mcp.services.qauth_client import QAuthClient
from quollnet_mcp.services.qflow_client import QFlowClient


qapp_client = QAppExtendedClient()
qauth_client = QAuthClient()
qflow_client = QFlowClient()

# Constructing a disabled client performs no network activity and requires no URL.
from quollnet_mcp.qledger.qledger_client import QledgerClient

qledger_client = QledgerClient(qauth_client.settings)
