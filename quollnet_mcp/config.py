import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    qapp_base_url: str
    qapp_timeout_seconds: float
    qflow_base_url: str
    qflow_timeout_seconds: float
    qauth_timeout_seconds: float
    cashflowpot_app_id: str
    service_version: str
    qauth_issuer_url: str
    mcp_resource_uri: str
    qauth_app_id: str
    qauth_public_key: str
    qapp_app_id: str


def get_settings() -> Settings:
    qauth_app_id = os.getenv("QAUTH_APP_ID")
    qauth_public_key = os.getenv("QAUTH_PUBLIC_KEY")
    qapp_app_id = os.getenv("QAPP_APP_ID")
    cashflowpot_app_id = os.getenv("CASHFLOWPOT_APP_ID")
    if not qauth_app_id:
        raise ValueError("QAUTH_APP_ID is required")
    if not qauth_public_key:
        raise ValueError("QAUTH_PUBLIC_KEY is required")
    if not qapp_app_id:
        raise ValueError("QAPP_APP_ID is required")
    if not cashflowpot_app_id:
        raise ValueError("CASHFLOWPOT_APP_ID is required")

    return Settings(
        qapp_base_url=os.getenv("QAPP_BASE_URL", "https://quollnet.com"),
        qapp_timeout_seconds=float(os.getenv("QAPP_TIMEOUT_SECONDS", "15")),
        qflow_base_url=os.getenv("QFLOW_BASE_URL", "https://quollnet.com/q_flow/"),
        qflow_timeout_seconds=float(os.getenv("QFLOW_TIMEOUT_SECONDS", "30")),
        qauth_timeout_seconds=float(os.getenv("QAUTH_TIMEOUT_SECONDS", "15")),
        cashflowpot_app_id=cashflowpot_app_id,
        service_version=os.getenv("QUOLLNET_VERSION", "0.1.0"),
        qauth_issuer_url=os.getenv("QAUTH_ISSUER_URL", "https://quollnet.com/api"),
        mcp_resource_uri=os.getenv("MCP_RESOURCE_URI", "https://mcp.quollnet.com/mcp"),
        qauth_app_id=qauth_app_id,
        qauth_public_key=qauth_public_key.replace("\\n", "\n"),
        qapp_app_id=qapp_app_id,
    )
