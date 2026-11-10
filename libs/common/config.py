import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Shared 12-factor settings inherited by all microservices."""
    service_name: str = "service"
    environment: str = "production"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql://postgres:postgres@db:5432/trade_ai"
    db_pool_min: int = 2
    db_pool_max: int = 10

    # Redis Backbone
    redis_url: str = "redis://:redis_password@redis:6379/0"
    redis_stream_maxlen_ticks: int = 10000
    redis_stream_maxlen_standard: int = 25000
    redis_dlq_max_retries: int = 3

    # Monitored Symbols
    tracked_symbols: Union[List[str], str] = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
        "XRPUSDT", "DOGEUSDT", "LINKUSDT", "TRXUSDT"
    ]
    tracked_timeframes: Union[List[str], str] = ["15m", "1h", "4h"]

    @field_validator("tracked_symbols", "tracked_timeframes", mode="after")
    @classmethod
    def parse_comma_separated_list(cls, v: Union[str, List[str]]):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

