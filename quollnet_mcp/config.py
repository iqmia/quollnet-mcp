import os
import math
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
    cashflowpot_mcp_resource_uri: str
    qauth_app_id: str
    qauth_public_key: str
    qapp_app_id: str
    qledger_enabled: bool = False
    qledger_app_id: str = ""
    qledger_base_url: str = ""
    qledger_timeout_seconds: float = 30
    qledger_mcp_resource_uri: str = "https://mcp.quollnet.com/qledger"
    qledger_max_file_bytes: int = 10485760
    qledger_max_batch_file_bytes: int = 20971520


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

    qledger_enabled = os.getenv("QLEDGER_ENABLED", "false").lower() == "true"
    if qledger_enabled and (
        not os.getenv("QLEDGER_APP_ID") or not os.getenv("QLEDGER_BASE_URL")
    ):
        raise ValueError(
            "QLEDGER_APP_ID and QLEDGER_BASE_URL are required when QLEDGER_ENABLED=true"
        )
    qledger_file_limit = (
        int(os.getenv("QLEDGER_MAX_FILE_BYTES", "10485760"))
        if qledger_enabled
        else 10485760
    )
    qledger_batch_limit = (
        int(os.getenv("QLEDGER_MAX_BATCH_FILE_BYTES", "20971520"))
        if qledger_enabled
        else 20971520
    )
    qledger_timeout = (
        float(os.getenv("QLEDGER_TIMEOUT_SECONDS", "30")) if qledger_enabled else 30
    )
    if not math.isfinite(qledger_timeout) or qledger_timeout <= 0:
        raise ValueError("QLEDGER_TIMEOUT_SECONDS must be finite and positive")
    if (
        not 1 <= qledger_file_limit <= 10485760
        or qledger_batch_limit < qledger_file_limit
    ):
        raise ValueError(
            "QLedger file limit must be 1–10485760 and batch limit at least the file limit"
        )

    return Settings(
        qledger_enabled=qledger_enabled,
        qledger_app_id=os.getenv("QLEDGER_APP_ID", ""),
        qledger_base_url=os.getenv("QLEDGER_BASE_URL", ""),
        qledger_timeout_seconds=qledger_timeout,
        qledger_mcp_resource_uri=os.getenv(
            "QLEDGER_MCP_RESOURCE_URI", "https://mcp.quollnet.com/qledger"
        ),
        qledger_max_file_bytes=qledger_file_limit,
        qledger_max_batch_file_bytes=qledger_batch_limit,
        qapp_base_url=os.getenv("QAPP_BASE_URL", "https://quollnet.com"),
        qapp_timeout_seconds=float(os.getenv("QAPP_TIMEOUT_SECONDS", "15")),
        qflow_base_url=os.getenv("QFLOW_BASE_URL", "https://quollnet.com/q_flow/"),
        qflow_timeout_seconds=float(os.getenv("QFLOW_TIMEOUT_SECONDS", "30")),
        qauth_timeout_seconds=float(os.getenv("QAUTH_TIMEOUT_SECONDS", "15")),
        cashflowpot_app_id=cashflowpot_app_id,
        service_version=os.getenv("QUOLLNET_VERSION", "0.1.0"),
        qauth_issuer_url=os.getenv("QAUTH_ISSUER_URL", "https://quollnet.com/api"),
        mcp_resource_uri=os.getenv("MCP_RESOURCE_URI", "https://mcp.quollnet.com/mcp"),
        cashflowpot_mcp_resource_uri=os.getenv(
            "CASHFLOWPOT_MCP_RESOURCE_URI",
            "https://mcp.quollnet.com/cashflowpot",
        ),
        qauth_app_id=qauth_app_id,
        qauth_public_key=qauth_public_key.replace("\\n", "\n"),
        qapp_app_id=qapp_app_id,
    )
