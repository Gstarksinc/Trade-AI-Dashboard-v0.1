"""Signal Service Configuration."""

from libs.common.config import BaseServiceSettings


class SignalSettings(BaseServiceSettings):
    service_name: str = "signal-service"
    consumer_group: str = "signal-service-group"
    consumer_name: str = "signal-worker-1"
    max_entry_wait_seconds: int = 86400  # 24 hours before expiration


settings = SignalSettings()

