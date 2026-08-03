import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    qapp_base_url: str
    qapp_timeout_seconds: float
    service_version: str


def get_settings() -> Settings:
    return Settings(
        qapp_base_url=os.getenv("QAPP_BASE_URL", "https://quollnet.com"),
        qapp_timeout_seconds=float(os.getenv("QAPP_TIMEOUT_SECONDS", "15")),
        service_version=os.getenv("QUOLLNET_VERSION", "0.1.0"),
    )
