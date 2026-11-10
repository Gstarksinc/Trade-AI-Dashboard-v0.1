"""Feature Service Configuration."""

from pydantic import Field
from libs.common.config import BaseServiceSettings


class FeatureSettings(BaseServiceSettings):
    service_name: str = "feature-service"
    feature_set_version: str = "v1.0.0"
    consumer_group: str = "feature-service-group"
    consumer_name: str = "feature-worker-1"
    lookback_bars: int = 300  # Number of historical closed bars required to compute rolling indicators
    btc_symbol: str = "BTCUSDT"


settings = FeatureSettings()

