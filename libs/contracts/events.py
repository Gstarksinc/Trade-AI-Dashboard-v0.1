from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class SignalStatus(str, Enum):
    WAITING_CONFIRMATION = "waiting_confirmation"
    WAITING_ENTRY = "waiting_entry"
    IN_PROGRESS = "in_progress"
    WIN_TARGET_HIT = "target_hit"
    LOSS_STOP_HIT = "stop_hit"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


class BaseEvent(BaseModel):
    """Base event model enforcing envelope standards across all services."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    event_version: str = "1.0"
    timestamp: Union[str, int] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    idempotency_key: str
    producer: str

    class Config:
        frozen = True


# ==============================================================================
# Service 1: market-collector events
# ==============================================================================

class PriceTickPayload(BaseModel):
    symbol: str
    price: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    volume_24h: float = 0.0
    quote_volume_24h: float = 0.0
    price_change_24h: float = 0.0
    index_price: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    funding_rate: Optional[float] = None
    mark_price: Optional[float] = None
    tick_dir: Optional[str] = None  # 'up', 'down', None
    ts: int = 0  # epoch milliseconds


class PriceTickEvent(BaseEvent):
    event_type: str = "price.tick"
    payload: PriceTickPayload


class CandleClosedPayload(BaseModel):
    symbol: str
    timeframe: str  # '1m', '15m', '1h', '4h'
    open_time: str  # ISO-8601 UTC
    close_time: str # ISO-8601 UTC
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0
    trades: int = 0
    trades_count: Optional[int] = None
    taker_buy_base: float = 0.0
    taker_buy_quote: float = 0.0
    taker_volume: Optional[float] = None


class CandleClosedEvent(BaseEvent):
    event_type: str = "candle.closed"
    payload: CandleClosedPayload


# ==============================================================================
# Service 2: feature-service events
# ==============================================================================

class FeaturesReadyPayload(BaseModel):
    symbol: str
    timeframe: str
    candle_open_time: Optional[str] = None
    bar_timestamp: Optional[str] = None
    feature_set_version: str
    features: Dict[str, float]
    close_price: Optional[float] = None

    def model_post_init(self, __context: Any) -> None:
        if self.candle_open_time is None and self.bar_timestamp is not None:
            object.__setattr__(self, "candle_open_time", self.bar_timestamp)
        elif self.bar_timestamp is None and self.candle_open_time is not None:
            object.__setattr__(self, "bar_timestamp", self.candle_open_time)


class FeaturesReadyEvent(BaseEvent):
    event_type: str = "features.ready"
    payload: FeaturesReadyPayload


# ==============================================================================
# Service 3: model-service events
# ==============================================================================

class PredictionReadyPayload(BaseModel):
    symbol: str
    timeframe: str
    candle_open_time: Union[datetime, str]
    direction: Direction
    probability: float = 0.0  # Platt/Isotonic calibrated
    meta_probability: Optional[float] = None
    raw_probability: Optional[float] = None
    calibrated_probability: Optional[float] = None
    meta_confidence: Optional[float] = None
    current_price: float = 0.0
    atr: float = 0.0
    model_version: str
    feature_set_version: str = "v1.0.0"
    is_shadow: bool = False

    def model_post_init(self, __context: Any) -> None:
        if self.probability == 0.0 and self.calibrated_probability is not None:
            object.__setattr__(self, "probability", self.calibrated_probability)
        if self.meta_probability is None and self.meta_confidence is not None:
            object.__setattr__(self, "meta_probability", self.meta_confidence)


class PredictionReadyEvent(BaseEvent):
    event_type: str = "prediction.ready"
    payload: PredictionReadyPayload


# ==============================================================================
# Service 5: risk-service events
# ==============================================================================

class SignalApprovedPayload(BaseModel):
    prediction_event_id: str
    symbol: str
    timeframe: str
    direction: Direction
    entry: float
    stop_loss: float
    take_profit: float
    atr: float
    position_size_usd: float
    leverage: float
    risk_pct: float
    reward_pct: float
    rr_ratio: float
    regime: str
    model_version: str
    feature_set_version: str
    candle_open_time: str
    expires_at: str


class SignalRiskDecisionPayload(BaseModel):
    symbol: str
    timeframe: str
    candle_open_time: Union[datetime, str]
    direction: str
    probability: float
    meta_probability: Optional[float] = None
    entry: float
    stop_loss: float
    take_profit: float
    position_size_usd: float
    leverage: float
    risk_reason: str


class SignalApprovedEvent(BaseEvent):
    event_type: str = "signal.approved"
    payload: SignalApprovedPayload


class SignalRejectedPayload(BaseModel):
    prediction_event_id: str
    symbol: str
    timeframe: str
    direction: Direction
    rejection_reason: str
    details: Dict[str, Any] = Field(default_factory=dict)


class SignalRejectedEvent(BaseEvent):
    event_type: str = "signal.rejected"
    payload: SignalRejectedPayload


# ==============================================================================
# Service 6: signal-service events
# ==============================================================================

class SignalStateChangedPayload(BaseModel):
    signal_id: int
    symbol: str
    timeframe: Optional[str] = "15m"
    direction: Optional[Union[Direction, str]] = "long"
    from_state: Optional[Union[SignalStatus, str]] = None
    to_state: Optional[Union[SignalStatus, str]] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    trigger_event: Optional[str] = None
    entry: Optional[float] = 0.0
    stop_loss: Optional[float] = 0.0
    take_profit: Optional[float] = 0.0
    trigger_price: Optional[float] = None
    cancel_reason: Optional[str] = None
    predicted_at: Optional[str] = ""
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    version: int = 1  # Optimistic lock sequence

    def model_post_init(self, __context: Any) -> None:
        if self.previous_state is None and self.from_state is not None:
            object.__setattr__(self, "previous_state", str(self.from_state))
        elif self.from_state is None and self.previous_state is not None:
            object.__setattr__(self, "from_state", self.previous_state)

        if self.new_state is None and self.to_state is not None:
            object.__setattr__(self, "new_state", str(self.to_state))
        elif self.to_state is None and self.new_state is not None:
            object.__setattr__(self, "to_state", self.new_state)


class SignalStateChangedEvent(BaseEvent):
    event_type: str = "signal.state_changed"
    payload: SignalStateChangedPayload


# ==============================================================================
# Service 7: paper-exec-service events
# ==============================================================================

class TradeClosedPayload(BaseModel):
    trade_id: int
    signal_id: int
    symbol: str
    timeframe: str
    direction: Direction
    entry: float
    exit_price: float
    leverage: float
    fees: float
    funding: float
    pnl_pct: float
    pnl_usd: float
    exit_reason: str
    opened_at: str
    closed_at: str
    predicted_at: str
    duration_sec: int
    time_to_target_sec: Optional[int] = None
    high_low_reconciled: bool = False


class TradeClosedEvent(BaseEvent):
    event_type: str = "trade.closed"
    payload: TradeClosedPayload


# ==============================================================================
# Dead-Letter Queue (DLQ) event
# ==============================================================================

class SystemDLQPayload(BaseModel):
    failed_service: str
    original_stream: str
    consumer_group: str
    error_type: str
    error_message: str
    raw_payload: str
    retry_count: int
    first_failed_at: str


class SystemDLQEvent(BaseEvent):
    event_type: str = "system.dlq"
    payload: SystemDLQPayload

