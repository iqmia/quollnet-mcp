import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    qapp_base_url: str
    qapp_timeout_seconds: float
    service_version: str
    qauth_issuer_url: str
    mcp_resource_uri: str
    qauth_app_id: str
    qauth_public_key: str


def get_settings() -> Settings:
    qauth_app_id = os.getenv("QAUTH_APP_ID")
    qauth_public_key = os.getenv("QAUTH_PUBLIC_KEY")
    if not qauth_app_id:
        raise ValueError("QAUTH_APP_ID is required")
    if not qauth_public_key:
        raise ValueError("QAUTH_PUBLIC_KEY is required")

    return Settings(
        qapp_base_url=os.getenv("QAPP_BASE_URL", "https://quollnet.com"),
        qapp_timeout_seconds=float(os.getenv("QAPP_TIMEOUT_SECONDS", "15")),
        service_version=os.getenv("QUOLLNET_VERSION", "0.1.0"),
        qauth_issuer_url=os.getenv("QAUTH_ISSUER_URL", "https://quollnet.com/api"),
        mcp_resource_uri=os.getenv("MCP_RESOURCE_URI", "https://mcp.quollnet.com/mcp"),
        qauth_app_id=qauth_app_id,
        qauth_public_key=qauth_public_key.replace("\\n", "\n"),
    )
