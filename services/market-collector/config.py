"""Market Collector Configuration."""

from typing import List, Union
from pydantic import Field, field_validator
from libs.common.config import BaseServiceSettings


class CollectorSettings(BaseServiceSettings):
    service_name: str = "market-collector"
    binance_fapi_url: str = Field(default="https://fapi.binance.com", env="BINANCE_FAPI_URL")
    binance_fapi_ws: str = Field(default="wss://fstream.binance.com/ws", env="BINANCE_FAPI_WS")
    binance_stream_url: str = Field(default="wss://fstream.binance.com/stream", env="BINANCE_STREAM_URL")
    
    symbols: Union[List[str], str] = [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "LINKUSDT",
        "TRXUSDT",
    ]
    timeframes: Union[List[str], str] = ["15m", "1h", "4h"]
    
    @field_validator("symbols", "timeframes", mode="after")
    @classmethod
    def parse_symbols_list(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v
    
    # Rate limit budget (weight per minute limit is 2400 on fapi; keep safe budget of 1200)
    rate_limit_weight_limit: int = 1200
    
    # Websocket / live polling intervals
    funding_poll_seconds: int = 3600
    oi_poll_seconds: int = 300
    gap_check_seconds: int = 1800
    enable_ws: bool = True
    enable_backfill_on_startup: bool = True


settings = CollectorSettings()

