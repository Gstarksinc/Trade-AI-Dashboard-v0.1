"""Paper Execution Service Configuration."""

from pydantic import Field
from libs.common.config import BaseServiceSettings


class PaperExecSettings(BaseServiceSettings):
    service_name: str = "paper-exec-service"
    consumer_group: str = "paper-exec-group"
    consumer_name: str = "paper-exec-worker-1"

    # Trade-through buffer: price must penetrate limit by at least 0.05%
    trade_through_buffer_pct: float = 0.0005
    taker_fee_pct: float = 0.0005     # 0.05% per leg
    slippage_pct: float = 0.0002      # 0.02% per leg
    initial_virtual_equity: float = 10000.0


settings = PaperExecSettings()

